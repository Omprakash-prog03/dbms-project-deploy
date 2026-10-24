from repositories.db_pool import db_pool
import datetime
import logging
from decimal import Decimal
from repositories.validation import money

class FeeRepository:
    @staticmethod
    def get_all_payments(student_id=None, semester_no=None):
        where_clauses = ["1=1"]
        params = []
        if student_id:
            where_clauses.append("fp.student_id = %s")
            params.append(student_id)
        if semester_no:
            where_clauses.append("fp.semester_no = %s")
            params.append(semester_no)
        where_sql = " AND ".join(where_clauses)

        sql = f"""
            SELECT fp.*, s.roll_no,
                   CONCAT(s.first_name, ' ', s.last_name) AS student_name,
                   d.dept_code
            FROM fee_payment fp
            JOIN student s ON fp.student_id = s.student_id
            JOIN department d ON s.dept_id = d.dept_id
            WHERE {where_sql}
            ORDER BY fp.paid_on DESC, fp.payment_id DESC
        """
        return db_pool.execute_query(sql, tuple(params), fetch="all")

    @staticmethod
    def get_defaulters():
        sql = """
            SELECT * FROM v_fee_status
            WHERE is_defaulter = 1
            ORDER BY balance_due DESC
        """
        return db_pool.execute_query(sql, fetch="all")

    @staticmethod
    def get_unpaid_students():
        sql = """
            SELECT * FROM v_fee_status
            WHERE payment_status = 'Unpaid'
            ORDER BY dept_code ASC, roll_no ASC
        """
        return db_pool.execute_query(sql, fetch="all")

    @staticmethod
    def get_fee_structures():
        sql = """
            SELECT fs.*, d.dept_code, d.dept_name
            FROM fee_structure fs
            JOIN department d ON fs.dept_id = d.dept_id
            ORDER BY d.dept_code ASC, fs.semester_no ASC
        """
        return db_pool.execute_query(sql, fetch="all")

    @staticmethod
    def get_missing_fee_structures():
        """
        Relational anti-join listing departments and semesters (1-8)
        that currently have NO fee structure configured in the database.
        """
        sql = """
            WITH RECURSIVE sem_seq(sem_no) AS (
                SELECT 1
                UNION ALL
                SELECT sem_no + 1 FROM sem_seq WHERE sem_no < 8
            )
            SELECT d.dept_id, d.dept_code, d.dept_name, s.sem_no AS semester_no
            FROM department d
            CROSS JOIN sem_seq s
            LEFT JOIN fee_structure fs ON d.dept_id = fs.dept_id AND s.sem_no = fs.semester_no
            WHERE fs.amount IS NULL
            ORDER BY d.dept_code ASC, s.sem_no ASC
        """
        return db_pool.execute_query(sql, fetch="all")

    @staticmethod
    def set_fee_structure(dept_id, semester_no, amount):
        amount = money(amount)
        dept_id, semester_no = int(dept_id), int(semester_no)
        if not 1 <= semester_no <= 8:
            raise ValueError("Semester must be between 1 and 8.")
        with db_pool.get_connection() as conn:
            cur = conn.cursor()
            def execute(sql, values):
                return cur.execute(sql if db_pool.is_mysql else sql.replace("%s", "?"), values)
            try:
                cur.execute("START TRANSACTION" if db_pool.is_mysql else "BEGIN IMMEDIATE")
                # Payments acquire this same row lock before checking their balance.
                execute("SELECT amount FROM fee_structure WHERE dept_id=%s AND semester_no=%s" +
                        (" FOR UPDATE" if db_pool.is_mysql else ""), (dept_id, semester_no))
                existing = cur.fetchone()
                execute("SELECT dept_id FROM department WHERE dept_id=%s", (dept_id,))
                if not cur.fetchone():
                    raise ValueError("Department not found.")
                execute("SELECT COALESCE(MAX(paid), 0) AS paid FROM "
                        "(SELECT SUM(fp.amount) AS paid FROM fee_payment fp "
                        "JOIN student s ON s.student_id=fp.student_id "
                        "WHERE s.dept_id=%s AND fp.semester_no=%s GROUP BY fp.student_id) totals",
                        (dept_id, semester_no))
                already_paid = Decimal(str(cur.fetchone()["paid"])).quantize(Decimal("0.01"))
                if amount < already_paid:
                    raise ValueError("The new fee cannot be lower than a student's recorded payments.")
                value = amount if db_pool.is_mysql else float(amount)
                if existing:
                    execute("UPDATE fee_structure SET amount=%s WHERE dept_id=%s AND semester_no=%s",
                            (value, dept_id, semester_no))
                else:
                    execute("INSERT INTO fee_structure (dept_id, semester_no, amount) VALUES (%s, %s, %s)",
                            (dept_id, semester_no, value))
                conn.commit()
                return True
            except Exception:
                conn.rollback()
                raise
            finally:
                cur.close()

    @staticmethod
    def record_payment(student_id, semester_no, amount, mode, receipt_no):
        """Atomically record a validated installment with overpayment protection."""
        try:
            amount = money(amount)
            student_id, semester_no = int(student_id), int(semester_no)
        except (ValueError, TypeError) as error:
            return {"status_code": 400, "message": str(error)}
        if not 1 <= semester_no <= 8:
            return {"status_code": 400, "message": "Semester must be between 1 and 8."}
        if mode not in ("Cash", "Card", "UPI", "Net Banking", "Demand Draft"):
            return {"status_code": 400, "message": "Choose a valid payment method."}
        receipt_no = receipt_no.strip() if isinstance(receipt_no, str) else ""
        if not receipt_no or len(receipt_no) > 50:
            return {"status_code": 400, "message": "Provide a receipt number of at most 50 characters."}

        with db_pool.get_connection() as conn:
            cur = conn.cursor()
            def execute(sql, values):
                return cur.execute(sql if db_pool.is_mysql else sql.replace("%s", "?"), values)
            try:
                cur.execute("START TRANSACTION" if db_pool.is_mysql else "BEGIN IMMEDIATE")
                lock = " FOR UPDATE" if db_pool.is_mysql else ""
                execute("SELECT dept_id, current_semester FROM student WHERE student_id=%s" + lock,
                        (student_id,))
                student = cur.fetchone()
                if not student:
                    conn.rollback()
                    return {"status_code": 404, "message": "Student does not exist."}
                if semester_no > student["current_semester"]:
                    conn.rollback()
                    return {"status_code": 400, "message": "A payment cannot be recorded for a future semester."}

                # Lock the price too, so an administrator cannot reduce it mid-payment.
                execute("SELECT amount FROM fee_structure WHERE dept_id=%s AND semester_no=%s" + lock,
                        (student["dept_id"], semester_no))
                fee_row = cur.fetchone()
                if not fee_row:
                    conn.rollback()
                    return {"status_code": 404, "message": "Fee structure not configured for this semester."}
                semester_fee = Decimal(str(fee_row["amount"])).quantize(Decimal("0.01"))
                execute("SELECT COALESCE(SUM(amount), 0) AS paid FROM fee_payment "
                        "WHERE student_id=%s AND semester_no=%s", (student_id, semester_no))
                already_paid = Decimal(str(cur.fetchone()["paid"])).quantize(Decimal("0.01"))
                max_payable = semester_fee - already_paid
                if amount > max_payable:
                    conn.rollback()
                    return {"status_code": 400, "message": f"Overpayment rejected. Maximum remaining fee payable: {max_payable:.2f}"}

                execute("INSERT INTO fee_payment (student_id, semester_no, amount, paid_on, mode, receipt_no) "
                        "VALUES (%s, %s, %s, %s, %s, %s)",
                        (student_id, semester_no, amount if db_pool.is_mysql else float(amount),
                         datetime.date.today().isoformat(), mode, receipt_no))
                payment_id = cur.lastrowid

                # MySQL's fee_payment trigger writes this audit row itself.
                if not db_pool.is_mysql:
                    audit_json = db_pool._json_object("student_id", student_id, "semester", semester_no,
                                                     "amount", str(amount), "receipt", receipt_no)
                    execute("INSERT INTO audit_log (table_name, action, record_id, new_values, changed_by) "
                            "VALUES ('fee_payment', 'INSERT', %s, %s, 'fee_clerk')", (payment_id, audit_json))
                conn.commit()
                return {"status_code": 200, "message": "Payment successfully recorded.", "payment_id": payment_id}
            except Exception as error:
                conn.rollback()
                if "fee_payment.receipt_no" in str(error) or (error.args and error.args[0] == 1062):
                    return {"status_code": 409, "message": "That receipt number has already been recorded."}
                logging.getLogger(__name__).exception("Payment recording failed")
                return {"status_code": 500, "message": "The payment could not be recorded. No changes were saved."}
            finally:
                cur.close()
