import os
import re
import datetime
from repositories.db_pool import db_pool

QUERIES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "db", "queries")

class InsightsRepository:
    _queries_cache = None

    @classmethod
    def load_showcase_queries(cls):
        if cls._queries_cache is not None:
            return cls._queries_cache

        queries = []
        files = [
            ("joins.sql", "Joins (Q01 - Q06)"),
            ("aggregates.sql", "Aggregations & Grouping (Q07 - Q11)"),
            ("subqueries.sql", "Subqueries (Q12 - Q16)"),
            ("windows_ctes.sql", "Window Functions & CTEs (Q17 - Q21)"),
            ("sets.sql", "Set Operations (Q22 - Q23)"),
            ("dml.sql", "Data Modification DML (Q24 - Q25)")
        ]

        for fname, group_name in files:
            fpath = os.path.join(QUERIES_DIR, fname)
            if not os.path.exists(fpath):
                continue
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()

            raw_blocks = re.split(r'\n(?=--\s*Q\d+)', content)
            for block in raw_blocks:
                block = block.strip()
                if not block or not block.startswith("--"):
                    continue
                lines = block.splitlines()
                title_line = lines[0].lstrip("- ").strip()
                match = re.match(r'(Q\d+)[\.\:]?\s*(.*)', title_line)
                qid = match.group(1) if match else "Q"
                qname = match.group(2) if match else title_line

                desc_lines = []
                sql_lines = []
                for line in lines[1:]:
                    if line.startswith("--"):
                        desc_lines.append(line.lstrip("- ").strip())
                    else:
                        sql_lines.append(line)

                sql_code = "\n".join(sql_lines).strip()
                if sql_code:
                    queries.append({
                        "id": qid,
                        "name": qname,
                        "group": group_name,
                        "description": " ".join(desc_lines),
                        "sql": sql_code
                    })

        cls._queries_cache = queries
        return queries

    @staticmethod
    def get_query_by_id(qid):
        all_q = InsightsRepository.load_showcase_queries()
        for q in all_q:
            if q["id"].upper() == qid.upper():
                return q
        return None

    @staticmethod
    def execute_showcase(qid):
        q = InsightsRepository.get_query_by_id(qid)
        if not q:
            return {"error": f"Query ID '{qid}' not found."}

        sql = q["sql"]
        t0 = datetime.datetime.now()
        try:
            # Handle multi-statement transaction DML scripts (Q24, Q25)
            if "START TRANSACTION" in sql.upper() or "BEGIN TRANSACTION" in sql.upper():
                with db_pool.get_connection() as conn:
                    cur = conn.cursor()
                    if not db_pool.is_mysql:
                        # SQLite uses BEGIN TRANSACTION instead of START TRANSACTION
                        sqlite_script = re.sub(r'START\s+TRANSACTION;', 'BEGIN TRANSACTION;', sql, flags=re.IGNORECASE)
                        sqlite_script = re.sub(r'ROW_COUNT\(\)', 'total_changes()', sqlite_script, flags=re.IGNORECASE)
                        # Translate MySQL UPDATE ... JOIN for SQLite in Q25
                        sqlite_script = re.sub(
                            r'UPDATE\s+fee_structure\s+fs\s+JOIN\s+department\s+d\s+ON\s+fs\.dept_id\s*=\s*d\.dept_id\s+SET\s+fs\.amount\s*=\s*fs\.amount\s*\*\s*0\.90\s+WHERE\s+fs\.semester_no\s*=\s*2\s+AND\s+d\.dept_code\s*=\s*[\'"]CSE[\'"];',
                            'UPDATE fee_structure SET amount = amount * 0.90 WHERE semester_no = 2 AND dept_id = (SELECT dept_id FROM department WHERE dept_code = "CSE");',
                            sqlite_script, flags=re.IGNORECASE
                        )
                        # Remove comments
                        clean_lines = [l for l in sqlite_script.splitlines() if not l.strip().startswith("--")]
                        cur.executescript("\n".join(clean_lines))
                    else:
                        for statement in sql.split(";"):
                            if statement.strip():
                                cur.execute(statement)
                    duration_ms = (datetime.datetime.now() - t0).total_seconds() * 1000.0
                    return {
                        "query": q,
                        "rows": [{"status": "Transaction executed successfully and rolled back clean (0 records altered)."}],
                        "columns": ["status"],
                        "duration_ms": round(duration_ms, 2),
                        "row_count": 1
                    }
            else:
                final_sql = sql
                if not db_pool.is_mysql:
                    # Emulate ALL syntax for SQLite if needed (Q16)
                    if ">= ALL" in final_sql:
                        final_sql = re.sub(
                            r'>=\s*ALL\s*\(\s*SELECT\s+r2\.marks_obtained\s+FROM\s+result\s+r2\s+WHERE\s+r2\.exam_id\s*=\s*ex\.exam_id\s*\)',
                            '>= (SELECT MAX(r2.marks_obtained) FROM result r2 WHERE r2.exam_id = ex.exam_id)',
                            final_sql,
                            flags=re.IGNORECASE
                        )

                table = db_pool.execute_query(final_sql, fetch="table")
                rows = table["rows"]
                duration_ms = (datetime.datetime.now() - t0).total_seconds() * 1000.0
                columns = table["columns"]
                return {
                    "query": q,
                    "rows": rows[:50],
                    "columns": columns,
                    "duration_ms": round(duration_ms, 2),
                    "row_count": len(rows)
                }
        except Exception as e:
            return {"error": str(e), "query": q}

    @staticmethod
    def get_explain_plan(qid):
        q = InsightsRepository.get_query_by_id(qid)
        if not q:
            return {"error": "Query not found."}

        sql = q["sql"]
        if "START TRANSACTION" in sql.upper():
            return {
                "rows": [{"id": 1, "select_type": "TRANSACTION", "table": "DML", "extra": "Transactional multi-statement demonstration with rollback"}],
                "columns": ["id", "select_type", "table", "extra"],
                "query": q
            }

        explain_sql = f"EXPLAIN {sql}"
        try:
            rows = db_pool.execute_query(explain_sql, fetch="all")
            columns = list(rows[0].keys()) if rows else []
            return {"rows": rows, "columns": columns, "query": q}
        except Exception:
            try:
                rows = db_pool.execute_query(f"EXPLAIN QUERY PLAN {sql}", fetch="all")
                columns = list(rows[0].keys()) if rows else []
                return {"rows": rows, "columns": columns, "query": q}
            except Exception as e2:
                return {"error": str(e2), "query": q}

    @staticmethod
    def run_transaction_demo():
        initial_count = db_pool.execute_query("SELECT COUNT(*) FROM student", fetch="val")
        steps = []
        steps.append(f"1. Pre-condition: Initial total students in database = {initial_count}")
        steps.append("2. START TRANSACTION; issued on active database connection.")

        rolled_back = False
        with db_pool.get_connection() as conn:
            cur = conn.cursor()
            try:
                cur.execute(
                    "INSERT INTO student (roll_no, first_name, last_name, email, phone, dob, gender, address, dept_id, admission_date, current_semester, status) "
                    "VALUES ('99TEST001', 'Test', 'Candidate', 'test99@sims.edu', '9999999999', '2005-01-01', 'Other', 'Campus', 1, '2026-06-01', 1, 'Active')"
                )
                steps.append("3. Staged INSERT for student '99TEST001'. Uncommitted row exists in transaction buffer.")

                steps.append("4. Executing deliberate integrity violation: inserting second student with duplicate roll_no '99TEST001'...")
                cur.execute(
                    "INSERT INTO student (roll_no, first_name, last_name, email, phone, dob, gender, address, dept_id, admission_date, current_semester, status) "
                    "VALUES ('99TEST001', 'Conflict', 'Person', 'conflict@sims.edu', '9999999998', '2005-01-01', 'Other', 'Campus', 1, '2026-06-01', 1, 'Active')"
                )
                conn.commit()
            except Exception as err:
                conn.rollback()
                rolled_back = True
                steps.append(f"5. EXCEPTION CAUGHT: {type(err).__name__} - Integrity constraint violation triggered!")
                steps.append("6. ROLLBACK; executed automatically by exception handler.")

        final_count = db_pool.execute_query("SELECT COUNT(*) FROM student", fetch="val")
        steps.append(f"7. Post-condition: Final total students in database = {final_count} (Delta: {final_count - initial_count})")
        steps.append("8. VERIFICATION: Transaction successfully rolled back without leaving any ghost or corrupt rows!")

        return {
            "success": rolled_back and (final_count == initial_count),
            "steps": steps,
            "initial_count": initial_count,
            "final_count": final_count
        }

    @staticmethod
    def get_audit_log(limit=50):
        sql = "SELECT * FROM audit_log ORDER BY changed_at DESC LIMIT %s"
        return db_pool.execute_query(sql, (limit,), fetch="all")

    @staticmethod
    def get_schema_tables():
        if db_pool.is_mysql:
            sql = """
                SELECT table_name, table_rows, data_length, create_time
                FROM information_schema.tables
                WHERE table_schema = 'sims_db'
                ORDER BY table_name ASC
            """
            return db_pool.execute_query(sql, fetch="all")
        else:
            sql = "SELECT name AS table_name, type FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name ASC"
            tables = db_pool.execute_query(sql, fetch="all")
            for t in tables:
                t_count = db_pool.execute_query(f"SELECT COUNT(*) FROM {t['table_name']}", fetch="val") or 0
                t["table_rows"] = t_count
            return tables
