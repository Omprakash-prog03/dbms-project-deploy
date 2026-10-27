import os
import re
import json
import sqlite3
import datetime
import threading
from contextlib import contextmanager
from config import Config
from repositories import dialect

# Global variable to store last executed SQL query + params for "Show SQL" inspection
_thread_local = threading.local()

def record_last_query(sql, params=None, duration_ms=0.0):
    if "password_hash" in sql.lower():
        return
    item = {
        "sql": sql.strip(),
        "params": [str(p) if not isinstance(p, (int, float, str)) else p for p in (params or [])],
        "duration_ms": round(duration_ms, 2)
    }
    if not hasattr(_thread_local, "queries"):
        _thread_local.queries = []
    _thread_local.queries.append(item)

def get_last_queries():
    # Request-local only: never leak another visitor's SQL or parameters.
    return list(getattr(_thread_local, "queries", []))[-40:]

def clear_last_queries():
    _thread_local.queries = []


# ============================================================================
# MYSQL / COMPATIBILITY ADAPTER WITH CONNECTION POOLING
# ============================================================================
class PopulationStdDev:
    def __init__(self):
        self.n = 0
        self.mean = 0.0
        self.m2 = 0.0
    def step(self, value):
        if value is not None:
            self.n += 1
            delta = float(value) - self.mean
            self.mean += delta / self.n
            self.m2 += delta * (float(value) - self.mean)
    def finalize(self):
        return (self.m2 / self.n) ** 0.5 if self.n else None


class DatabasePool:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(DatabasePool, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self.is_mysql = False
        self.pool = None
        self._init_connection()

    def _init_connection(self):
        if Config.DB_ENGINE == "sqlite":
            self._init_embedded_db()
            return
        # First attempt: Try connecting to real MySQL 8
        try:
            import pymysql
            conn = pymysql.connect(
                host=Config.DB_HOST,
                port=Config.DB_PORT,
                user=Config.DB_USER,
                password=Config.DB_PASSWORD,
                database=Config.DB_NAME,
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor,
                connect_timeout=2
            )
            conn.close()
            self.is_mysql = True
            print(f"[DB] Successfully connected to live MySQL 8 on {Config.DB_HOST}:{Config.DB_PORT}/{Config.DB_NAME}")
        except Exception as e:
            if Config.DB_ENGINE == "mysql":
                raise RuntimeError("Configured MySQL database is unavailable.") from e
            self.is_mysql = False
            print(f"[DB] Live MySQL 8 not reachable ({e}). Initializing high-fidelity embedded relational engine.")
            self._init_embedded_db()

    def _init_embedded_db(self, db_path="sims_embedded.db"):
        self.db_path = Config.SQLITE_PATH
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        # Ensure directory exists and schema is populated
        self._bootstrap_embedded_schema()

    def _bootstrap_embedded_schema(self):
        conn = self._get_raw_sqlite()
        cur = conn.cursor()

        # Check if tables exist
        cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='student'")
        if cur.fetchone()[0] == 0:
            print("[DB] Initializing embedded schema and constraints...")
            self._create_sqlite_schema(conn)
        if conn.execute("PRAGMA user_version").fetchone()[0] < 2:
            migration = os.path.join(os.path.dirname(os.path.dirname(__file__)), "db", "embedded_guards.sql")
            with open(migration, encoding="utf-8") as source:
                conn.executescript(source.read())
        conn.close()

    def _get_raw_sqlite(self):
        conn = sqlite3.connect(self.db_path, timeout=30.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")

        # Register custom MySQL functions in SQLite
        conn.create_function("CONCAT", -1, lambda *args: "".join(str(a) for a in args if a is not None))
        conn.create_function("fn_grade", 1, self._fn_grade)
        conn.create_function("fn_attendance_pct", 1, lambda enr_id: self._fn_attendance_pct(conn, enr_id))
        conn.create_function("fn_student_cgpa", 1, lambda stu_id: self._fn_student_cgpa(conn, stu_id))
        conn.create_function("CURDATE", 0, lambda: datetime.date.today().isoformat())
        conn.create_function("NOW", 0, lambda: datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        conn.create_function("JSON_OBJECT", -1, self._json_object)
        conn.create_aggregate("STDDEV", 1, PopulationStdDev)
        conn.create_function("DATE_FORMAT", 2, self._date_format)
        conn.create_function("MONTH", 1, lambda d: int(d.split("-")[1]) if d and "-" in str(d) else 1)
        conn.create_function("YEAR", 1, lambda d: int(d.split("-")[0]) if d and "-" in str(d) else 2026)
        return conn

    @staticmethod
    def _fn_grade(pct):
        if pct is None:
            return None
        p = float(pct)
        if p >= 90.0: return "A+"
        elif p >= 80.0: return "A"
        elif p >= 70.0: return "B+"
        elif p >= 60.0: return "B"
        elif p >= 50.0: return "C"
        elif p >= 40.0: return "P"
        else: return "F"

    @staticmethod
    def _fn_attendance_pct(conn, enr_id):
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*), SUM(CASE WHEN status IN ('Present', 'Late') THEN 1 ELSE 0 END) FROM attendance WHERE enrollment_id = ?", (enr_id,))
        row = cur.fetchone()
        if not row or row[0] == 0:
            return 0.0
        return round((row[1] / row[0]) * 100, 2)

    @staticmethod
    def _fn_student_cgpa(conn, stu_id):
        # Each graded offering contributes one credit-weighted grade point.
        rows = conn.execute("""
            SELECT c.credits, 100.0 * SUM(r.marks_obtained) / SUM(ex.max_marks) AS percentage
            FROM enrollment e
            JOIN course_offering co ON co.offering_id=e.offering_id
            JOIN course c ON c.course_id=co.course_id
            JOIN result r ON r.enrollment_id=e.enrollment_id
            JOIN exam ex ON ex.exam_id=r.exam_id AND ex.offering_id=e.offering_id
            WHERE e.student_id=? AND e.status!='Dropped'
            GROUP BY e.enrollment_id, c.credits
        """, (stu_id,)).fetchall()
        credits = sum(row[0] for row in rows)
        def points(p):
            for threshold, value in ((90,10),(80,9),(70,8),(60,7),(50,6),(40,5)):
                if p >= threshold:
                    return value
            return 0
        return round(sum(row[0] * points(row[1]) for row in rows) / credits, 2) if credits else 0.0

    @staticmethod
    def _json_object(*args):
        data = {}
        for i in range(0, len(args), 2):
            if i + 1 < len(args):
                data[str(args[i])] = args[i+1]
        return json.dumps(data)

    @staticmethod
    def _date_format(date_val, fmt_str):
        if not date_val:
            return ""
        try:
            d = datetime.datetime.strptime(str(date_val)[:10], "%Y-%m-%d")
            if fmt_str == '%Y-%m': return d.strftime("%Y-%m")
            if fmt_str == '%b': return d.strftime("%b")
            if fmt_str == '%y': return d.strftime("%y")
            return d.strftime("%Y-%m-%d")
        except Exception:
            return str(date_val)

    def _create_sqlite_schema(self, conn):
        cur = conn.cursor()
        cur.executescript("""
        CREATE TABLE IF NOT EXISTS department (
            dept_id INTEGER PRIMARY KEY AUTOINCREMENT,
            dept_code TEXT NOT NULL UNIQUE,
            dept_name TEXT NOT NULL UNIQUE,
            hod_faculty_id INTEGER NULL,
            established_year INTEGER NOT NULL CHECK (established_year >= 1900)
        );

        CREATE TABLE IF NOT EXISTS faculty (
            faculty_id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            phone TEXT NOT NULL,
            dept_id INTEGER NOT NULL,
            designation TEXT NOT NULL CHECK(designation IN ('Professor', 'Associate Professor', 'Assistant Professor', 'Lecturer')),
            hire_date TEXT NOT NULL,
            salary REAL NOT NULL CHECK (salary > 0),
            status TEXT NOT NULL DEFAULT 'Active' CHECK(status IN ('Active', 'On Leave', 'Resigned', 'Retired')),
            FOREIGN KEY (dept_id) REFERENCES department(dept_id) ON DELETE RESTRICT ON UPDATE CASCADE
        );

        CREATE TABLE IF NOT EXISTS student (
            student_id INTEGER PRIMARY KEY AUTOINCREMENT,
            roll_no TEXT NOT NULL UNIQUE,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            phone TEXT NOT NULL,
            dob TEXT NOT NULL,
            gender TEXT NOT NULL CHECK(gender IN ('Male', 'Female', 'Other')),
            address TEXT NOT NULL,
            dept_id INTEGER NOT NULL,
            admission_date TEXT NOT NULL,
            current_semester INTEGER NOT NULL DEFAULT 1 CHECK (current_semester BETWEEN 1 AND 8),
            status TEXT NOT NULL DEFAULT 'Active' CHECK(status IN ('Active', 'Graduated', 'Suspended', 'Dropped')),
            photo_url TEXT NULL,
            FOREIGN KEY (dept_id) REFERENCES department(dept_id) ON DELETE RESTRICT ON UPDATE CASCADE
        );

        CREATE TABLE IF NOT EXISTS guardian (
            guardian_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            relation TEXT NOT NULL,
            phone TEXT NOT NULL,
            FOREIGN KEY (student_id) REFERENCES student(student_id) ON DELETE CASCADE ON UPDATE CASCADE
        );

        CREATE TABLE IF NOT EXISTS course (
            course_id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_code TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            credits INTEGER NOT NULL CHECK (credits BETWEEN 1 AND 6),
            dept_id INTEGER NOT NULL,
            semester_no INTEGER NOT NULL CHECK (semester_no BETWEEN 1 AND 8),
            FOREIGN KEY (dept_id) REFERENCES department(dept_id) ON DELETE RESTRICT ON UPDATE CASCADE
        );

        CREATE TABLE IF NOT EXISTS course_offering (
            offering_id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            faculty_id INTEGER NOT NULL,
            academic_year TEXT NOT NULL,
            term TEXT NOT NULL CHECK(term IN ('Fall', 'Spring', 'Summer')),
            capacity INTEGER NOT NULL CHECK (capacity > 0),
            enrolled_count INTEGER NOT NULL DEFAULT 0 CHECK (enrolled_count >= 0),
            UNIQUE(course_id, academic_year, term),
            FOREIGN KEY (course_id) REFERENCES course(course_id) ON DELETE RESTRICT ON UPDATE CASCADE,
            FOREIGN KEY (faculty_id) REFERENCES faculty(faculty_id) ON DELETE RESTRICT ON UPDATE CASCADE
        );

        CREATE TABLE IF NOT EXISTS enrollment (
            enrollment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            offering_id INTEGER NOT NULL,
            enroll_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Enrolled' CHECK(status IN ('Enrolled', 'Dropped', 'Completed')),
            UNIQUE(student_id, offering_id),
            FOREIGN KEY (student_id) REFERENCES student(student_id) ON DELETE RESTRICT ON UPDATE CASCADE,
            FOREIGN KEY (offering_id) REFERENCES course_offering(offering_id) ON DELETE RESTRICT ON UPDATE CASCADE
        );

        CREATE TABLE IF NOT EXISTS attendance (
            attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
            enrollment_id INTEGER NOT NULL,
            class_date TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('Present', 'Absent', 'Late')),
            UNIQUE(enrollment_id, class_date),
            FOREIGN KEY (enrollment_id) REFERENCES enrollment(enrollment_id) ON DELETE CASCADE ON UPDATE CASCADE
        );

        CREATE TABLE IF NOT EXISTS exam (
            exam_id INTEGER PRIMARY KEY AUTOINCREMENT,
            offering_id INTEGER NOT NULL,
            exam_type TEXT NOT NULL CHECK(exam_type IN ('Internal', 'Midterm', 'Final')),
            max_marks REAL NOT NULL CHECK (max_marks > 0),
            exam_date TEXT NOT NULL,
            UNIQUE(offering_id, exam_type),
            FOREIGN KEY (offering_id) REFERENCES course_offering(offering_id) ON DELETE CASCADE ON UPDATE CASCADE
        );

        CREATE TABLE IF NOT EXISTS result (
            result_id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER NOT NULL,
            enrollment_id INTEGER NOT NULL,
            marks_obtained REAL NOT NULL CHECK (marks_obtained >= 0),
            UNIQUE(exam_id, enrollment_id),
            FOREIGN KEY (exam_id) REFERENCES exam(exam_id) ON DELETE RESTRICT ON UPDATE CASCADE,
            FOREIGN KEY (enrollment_id) REFERENCES enrollment(enrollment_id) ON DELETE CASCADE ON UPDATE CASCADE
        );

        CREATE TABLE IF NOT EXISTS fee_structure (
            dept_id INTEGER NOT NULL,
            semester_no INTEGER NOT NULL CHECK (semester_no BETWEEN 1 AND 8),
            amount REAL NOT NULL CHECK (amount > 0),
            PRIMARY KEY (dept_id, semester_no),
            FOREIGN KEY (dept_id) REFERENCES department(dept_id) ON DELETE CASCADE ON UPDATE CASCADE
        );

        CREATE TABLE IF NOT EXISTS fee_payment (
            payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            semester_no INTEGER NOT NULL CHECK (semester_no BETWEEN 1 AND 8),
            amount REAL NOT NULL CHECK (amount > 0),
            paid_on TEXT NOT NULL,
            mode TEXT NOT NULL CHECK(mode IN ('Cash', 'Card', 'UPI', 'Net Banking', 'Demand Draft')),
            receipt_no TEXT NOT NULL UNIQUE,
            FOREIGN KEY (student_id) REFERENCES student(student_id) ON DELETE RESTRICT ON UPDATE CASCADE
        );

        CREATE TABLE IF NOT EXISTS admission_application (
            application_id INTEGER PRIMARY KEY AUTOINCREMENT,
            applicant_name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            dept_id INTEGER NOT NULL,
            applied_on TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending' CHECK(status IN ('Pending', 'Approved', 'Rejected')),
            reviewed_by INTEGER NULL,
            reviewed_on TEXT NULL,
            FOREIGN KEY (dept_id) REFERENCES department(dept_id) ON DELETE RESTRICT ON UPDATE CASCADE,
            FOREIGN KEY (reviewed_by) REFERENCES faculty(faculty_id) ON DELETE SET NULL ON UPDATE CASCADE
        );

        CREATE TABLE IF NOT EXISTS app_user (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'faculty', 'student')),
            student_id INTEGER NULL,
            faculty_id INTEGER NULL,
            FOREIGN KEY (student_id) REFERENCES student(student_id) ON DELETE CASCADE ON UPDATE CASCADE,
            FOREIGN KEY (faculty_id) REFERENCES faculty(faculty_id) ON DELETE CASCADE ON UPDATE CASCADE
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_name TEXT NOT NULL,
            action TEXT NOT NULL CHECK(action IN ('INSERT', 'UPDATE', 'DELETE')),
            record_id INTEGER NOT NULL,
            old_values TEXT NULL,
            new_values TEXT NULL,
            changed_by TEXT NOT NULL,
            changed_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        );

        -- Secondary Indexes
        CREATE INDEX IF NOT EXISTS idx_enrollment_offering_student ON enrollment(offering_id, student_id);
        CREATE INDEX IF NOT EXISTS idx_student_dept_status ON student(dept_id, status);
        CREATE INDEX IF NOT EXISTS idx_payment_student_sem ON fee_payment(student_id, semester_no);
        CREATE INDEX IF NOT EXISTS idx_attendance_date_status ON attendance(class_date, status);
        CREATE INDEX IF NOT EXISTS idx_result_exam_marks ON result(exam_id, marks_obtained);
        CREATE INDEX IF NOT EXISTS idx_application_status_date ON admission_application(status, applied_on);

        -- Triggers for Enrolled Count Synchronizer
        CREATE TRIGGER IF NOT EXISTS trg_enr_inc AFTER INSERT ON enrollment
        WHEN NEW.status = 'Enrolled'
        BEGIN
            UPDATE course_offering SET enrolled_count = enrolled_count + 1 WHERE offering_id = NEW.offering_id;
        END;

        CREATE TRIGGER IF NOT EXISTS trg_enr_upd AFTER UPDATE ON enrollment
        BEGIN
            UPDATE course_offering SET enrolled_count = enrolled_count - 1
            WHERE offering_id = NEW.offering_id AND OLD.status = 'Enrolled' AND NEW.status != 'Enrolled';
            UPDATE course_offering SET enrolled_count = enrolled_count + 1
            WHERE offering_id = NEW.offering_id AND OLD.status != 'Enrolled' AND NEW.status = 'Enrolled';
        END;

        CREATE TRIGGER IF NOT EXISTS trg_enr_del AFTER DELETE ON enrollment
        WHEN OLD.status = 'Enrolled'
        BEGIN
            UPDATE course_offering SET enrolled_count = MAX(0, enrolled_count - 1) WHERE offering_id = OLD.offering_id;
        END;

        -- Trigger for Max Marks Ceiling
        CREATE TRIGGER IF NOT EXISTS trg_res_chk BEFORE INSERT ON result
        WHEN NEW.marks_obtained > (SELECT max_marks FROM exam WHERE exam_id = NEW.exam_id)
        BEGIN
            SELECT RAISE(ABORT, 'Integrity violation: marks_obtained cannot exceed exam max_marks.');
        END;

        CREATE TRIGGER IF NOT EXISTS trg_res_chk_upd BEFORE UPDATE ON result
        WHEN NEW.marks_obtained > (SELECT max_marks FROM exam WHERE exam_id = NEW.exam_id)
        BEGIN
            SELECT RAISE(ABORT, 'Integrity violation: marks_obtained cannot exceed exam max_marks.');
        END;

        -- Trigger for Capacity Limit
        CREATE TRIGGER IF NOT EXISTS trg_enr_cap BEFORE INSERT ON enrollment
        WHEN (SELECT enrolled_count FROM course_offering WHERE offering_id = NEW.offering_id) >=
             (SELECT capacity FROM course_offering WHERE offering_id = NEW.offering_id)
        BEGIN
            SELECT RAISE(ABORT, 'Registration rejected: Course offering has reached maximum seating capacity.');
        END;

        -- Trigger for Inactive Student
        CREATE TRIGGER IF NOT EXISTS trg_enr_active BEFORE INSERT ON enrollment
        WHEN (SELECT status FROM student WHERE student_id = NEW.student_id) != 'Active'
        BEGIN
            SELECT RAISE(ABORT, 'Registration rejected: Student profile is not Active.');
        END;

        -- Views
        CREATE VIEW IF NOT EXISTS v_student_overview AS
        SELECT
            s.student_id,
            s.roll_no,
            s.first_name || ' ' || s.last_name AS full_name,
            s.email,
            s.phone,
            s.gender,
            s.current_semester,
            s.status,
            s.admission_date,
            d.dept_id,
            d.dept_code,
            d.dept_name,
            COUNT(DISTINCT e.offering_id) AS total_courses_enrolled,
            ROUND(COALESCE(AVG(r.marks_obtained), 0), 2) AS average_marks
        FROM student s
        JOIN department d ON s.dept_id = d.dept_id
        LEFT JOIN enrollment e ON s.student_id = e.student_id AND e.status = 'Enrolled'
        LEFT JOIN result r ON e.enrollment_id = r.enrollment_id
        GROUP BY s.student_id, d.dept_id, s.admission_date;

        CREATE VIEW IF NOT EXISTS v_course_offering_stats AS
        SELECT
            co.offering_id,
            c.course_id,
            c.course_code,
            c.title AS course_title,
            c.credits,
            d.dept_id,
            d.dept_code,
            d.dept_name,
            co.faculty_id,
            f.first_name || ' ' || f.last_name AS instructor_name,
            co.academic_year,
            co.term,
            co.capacity,
            co.enrolled_count,
            ROUND((CAST(co.enrolled_count AS REAL) / co.capacity) * 100, 1) AS utilization_pct,
            CASE
                WHEN co.enrolled_count >= co.capacity THEN 'FULL'
                WHEN co.enrolled_count >= (co.capacity * 0.8) THEN 'ALMOST FULL'
                ELSE 'AVAILABLE'
            END AS seat_status
        FROM course_offering co
        JOIN course c ON co.course_id = c.course_id
        JOIN department d ON c.dept_id = d.dept_id
        JOIN faculty f ON co.faculty_id = f.faculty_id;

        CREATE VIEW IF NOT EXISTS v_fee_status AS
        SELECT
            s.student_id,
            s.roll_no,
            s.first_name || ' ' || s.last_name AS full_name,
            d.dept_id,
            d.dept_code,
            s.current_semester,
            fs.amount AS semester_fee_due,
            ROUND(COALESCE(SUM(fp.amount), 0), 2) AS total_paid,
            ROUND(fs.amount - ROUND(COALESCE(SUM(fp.amount), 0), 2), 2) AS balance_due,
            CASE
                WHEN ROUND(COALESCE(SUM(fp.amount), 0), 2) >= fs.amount THEN 'Fully Paid'
                WHEN ROUND(COALESCE(SUM(fp.amount), 0), 2) > 0 THEN 'Partial'
                ELSE 'Unpaid'
            END AS payment_status,
            CASE
                WHEN ROUND(fs.amount - ROUND(COALESCE(SUM(fp.amount), 0), 2), 2) > 0 THEN 1
                ELSE 0
            END AS is_defaulter
        FROM student s
        JOIN department d ON s.dept_id = d.dept_id
        JOIN fee_structure fs ON d.dept_id = fs.dept_id AND s.current_semester = fs.semester_no
        LEFT JOIN fee_payment fp ON s.student_id = fp.student_id AND s.current_semester = fp.semester_no
        WHERE s.status = 'Active'
        GROUP BY s.student_id, fs.amount;

        CREATE VIEW IF NOT EXISTS v_attendance_summary AS
        SELECT
            e.enrollment_id,
            s.student_id,
            s.roll_no,
            s.first_name || ' ' || s.last_name AS student_name,
            c.course_code,
            c.title AS course_title,
            co.academic_year,
            co.term,
            COUNT(a.attendance_id) AS total_classes,
            SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) AS present_count,
            SUM(CASE WHEN a.status = 'Late' THEN 1 ELSE 0 END) AS late_count,
            SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) AS absent_count,
            ROUND(
                (CAST(SUM(CASE WHEN a.status IN ('Present', 'Late') THEN 1 ELSE 0 END) AS REAL) /
                NULLIF(COUNT(a.attendance_id), 0)) * 100, 1
            ) AS attendance_percentage
        FROM enrollment e
        JOIN student s ON e.student_id = s.student_id
        JOIN course_offering co ON e.offering_id = co.offering_id
        JOIN course c ON co.course_id = c.course_id
        LEFT JOIN attendance a ON e.enrollment_id = a.enrollment_id
        GROUP BY e.enrollment_id;

        CREATE VIEW IF NOT EXISTS v_pending_approvals AS
        SELECT
            aa.application_id,
            aa.applicant_name,
            aa.email,
            aa.phone,
            d.dept_id,
            d.dept_code,
            d.dept_name,
            aa.applied_on,
            aa.status
        FROM admission_application aa
        JOIN department d ON aa.dept_id = d.dept_id
        WHERE aa.status = 'Pending'
        ORDER BY aa.applied_on ASC;
        """)
        conn.commit()

    @contextmanager
    def get_connection(self):
        if self.is_mysql:
            import pymysql
            conn = pymysql.connect(
                host=Config.DB_HOST,
                port=Config.DB_PORT,
                user=Config.DB_USER,
                password=Config.DB_PASSWORD,
                database=Config.DB_NAME,
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=False
            )
            try:
                yield conn
            finally:
                conn.close()
        else:
            conn = self._get_raw_sqlite()
            try:
                yield conn
            finally:
                conn.close()

    def execute_query(self, sql, params=None, fetch="all"):
        t0 = datetime.datetime.now()
        params = params or ()
        with self.get_connection() as conn:
            cur = conn.cursor()

            # Format query for engine
            final_sql = sql
            if not self.is_mysql:
                # Oracle syntax is accepted here, then spelled the way the
                # embedded engine expects it. Anything already portable passes
                # through untouched.
                final_sql, _notes = dialect.to_engine(sql)
                # Replace %s with ? for SQLite
                final_sql = re.sub(r'%s', '?', final_sql)

            try:
                cur.execute(final_sql, params)
                duration_ms = (datetime.datetime.now() - t0).total_seconds() * 1000.0
                record_last_query(sql, params, duration_ms)

                if fetch == "table":
                    rows = cur.fetchall() if self.is_mysql else [dict(row) for row in cur.fetchall()]
                    return {"rows": rows, "columns": [column[0] for column in (cur.description or [])]}
                if fetch == "all":
                    if self.is_mysql:
                        rows = cur.fetchall()
                    else:
                        rows = [dict(row) for row in cur.fetchall()]
                    return rows
                elif fetch == "one":
                    if self.is_mysql:
                        row = cur.fetchone()
                    else:
                        r = cur.fetchone()
                        row = dict(r) if r else None
                    return row
                elif fetch == "val":
                    r = cur.fetchone()
                    if not r: return None
                    if self.is_mysql:
                        return list(r.values())[0]
                    else:
                        return r[0]
            finally:
                cur.close()

    def execute_dml(self, sql, params=None, commit=True):
        t0 = datetime.datetime.now()
        params = params or ()
        with self.get_connection() as conn:
            cur = conn.cursor()
            final_sql = sql
            if not self.is_mysql:
                final_sql, _notes = dialect.to_engine(sql)
                final_sql = re.sub(r'%s', '?', final_sql)
            try:
                cur.execute(final_sql, params)
                if commit:
                    conn.commit()
                last_id = cur.lastrowid
                row_count = cur.rowcount
                duration_ms = (datetime.datetime.now() - t0).total_seconds() * 1000.0
                record_last_query(sql, params, duration_ms)
                return {"lastrowid": last_id, "rowcount": row_count}
            except Exception:
                if commit:
                    conn.rollback()
                raise
            finally:
                cur.close()

# Module level singleton instance
db_pool = DatabasePool()
