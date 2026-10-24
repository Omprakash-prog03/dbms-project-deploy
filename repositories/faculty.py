from repositories.db_pool import db_pool
import re
import math
import datetime
import bcrypt

class FacultyRepository:
    @staticmethod
    def get_all(dept_id=None):
        where_clauses = ["1=1"]
        params = []
        if dept_id:
            where_clauses.append("f.dept_id = %s")
            params.append(dept_id)
        where_sql = " AND ".join(where_clauses)

        sql = f"""
            SELECT f.*, d.dept_code, d.dept_name,
                   CONCAT(f.first_name, ' ', f.last_name) AS full_name,
                   CASE WHEN f.faculty_id = d.hod_faculty_id THEN 1 ELSE 0 END AS is_hod
            FROM faculty f
            JOIN department d ON f.dept_id = d.dept_id
            WHERE {where_sql}
            ORDER BY d.dept_code ASC, f.first_name ASC
        """
        return db_pool.execute_query(sql, tuple(params), fetch="all")

    @staticmethod
    def get_by_id(faculty_id):
        sql = """
            SELECT f.*, d.dept_code, d.dept_name,
                   CONCAT(f.first_name, ' ', f.last_name) AS full_name
            FROM faculty f
            JOIN department d ON f.dept_id = d.dept_id
            WHERE f.faculty_id = %s
        """
        return db_pool.execute_query(sql, (faculty_id,), fetch="one")

    @staticmethod
    def get_departments():
        sql = """
            SELECT d.*,
                   CONCAT(f.first_name, ' ', f.last_name) AS hod_name,
                   COUNT(DISTINCT s.student_id) AS student_count,
                   COUNT(DISTINCT c.course_id) AS course_count
            FROM department d
            LEFT JOIN faculty f ON d.hod_faculty_id = f.faculty_id
            LEFT JOIN student s ON d.dept_id = s.dept_id
            LEFT JOIN course c ON d.dept_id = c.dept_id
            GROUP BY d.dept_id
            ORDER BY d.dept_code ASC
        """
        return db_pool.execute_query(sql, fetch="all")

    @staticmethod
    def get_offerings_by_faculty(faculty_id):
        sql = """
            SELECT co.*, c.course_code, c.title AS course_title, c.credits,
                   ROUND(((co.enrolled_count * 1.0) / co.capacity) * 100, 1) AS utilization_pct
            FROM course_offering co
            JOIN course c ON co.course_id = c.course_id
            WHERE co.faculty_id = %s
            ORDER BY co.academic_year DESC, c.course_code ASC
        """
        return db_pool.execute_query(sql, (faculty_id,), fetch="all")

    @staticmethod
    def create(first_name, last_name, email, phone, dept_id, designation, hire_date, salary, status="Active", initial_password=""):
        if not first_name.strip() or not last_name.strip():
            raise ValueError("First and last name are required.")
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            raise ValueError("Enter a valid email address.")
        if not math.isfinite(float(salary)) or float(salary) <= 0:
            raise ValueError("Salary must be a finite positive amount.")
        datetime.date.fromisoformat(hire_date)
        if len(initial_password) < 8 or len(initial_password.encode("utf-8")) > 72:
            raise ValueError("Initial password must be at least 8 characters and at most 72 UTF-8 bytes.")
        pw_hash = bcrypt.hashpw(initial_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        # Faculty and login provisioning are one transaction; no half-created accounts.
        with db_pool.get_connection() as conn:
            cur = conn.cursor()
            def execute(sql, params):
                cur.execute(sql if db_pool.is_mysql else sql.replace("%s", "?"), params)
            try:
                cur.execute("START TRANSACTION" if db_pool.is_mysql else "BEGIN IMMEDIATE")
                execute("INSERT INTO faculty (first_name,last_name,email,phone,dept_id,designation,hire_date,salary,status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)", (first_name,last_name,email,phone,dept_id,designation,hire_date,salary,status))
                faculty_id = cur.lastrowid
                username = email.split("@")[0].lower()
                execute("SELECT user_id FROM app_user WHERE username=%s", (username,))
                if cur.fetchone():
                    username = f"{username}{faculty_id}"
                execute("INSERT INTO app_user (username,password_hash,role,faculty_id,student_id) VALUES (%s,%s,'faculty',%s,NULL)", (username,pw_hash,faculty_id))
                conn.commit()
                return faculty_id
            except Exception:
                conn.rollback()
                raise
            finally:
                cur.close()

    @staticmethod
    def update(faculty_id, first_name, last_name, email, phone, dept_id, designation, salary, status):
        sql = """
            UPDATE faculty
            SET first_name = %s, last_name = %s, email = %s, phone = %s,
                dept_id = %s, designation = %s, salary = %s, status = %s
            WHERE faculty_id = %s
        """
        params = (first_name, last_name, email, phone, dept_id, designation, salary, status, faculty_id)
        return db_pool.execute_dml(sql, params)["rowcount"]

    @staticmethod
    def delete(faculty_id):
        # Remove app_user first if linked
        db_pool.execute_dml("DELETE FROM app_user WHERE faculty_id = %s", (faculty_id,))
        sql = "DELETE FROM faculty WHERE faculty_id = %s"
        return db_pool.execute_dml(sql, (faculty_id,))["rowcount"]
