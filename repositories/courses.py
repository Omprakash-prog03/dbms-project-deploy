from repositories.db_pool import db_pool
import re

class CourseRepository:
    @staticmethod
    def get_all(dept_id=None, semester_no=None, search=None):
        where_clauses = ["1=1"]
        params = []
        if dept_id:
            where_clauses.append("c.dept_id = %s")
            params.append(dept_id)
        if search:
            where_clauses.append("(c.title LIKE %s OR c.course_code LIKE %s)")
            params.extend([f"%{search}%"] * 2)
        if semester_no:
            where_clauses.append("c.semester_no = %s")
            params.append(semester_no)
        where_sql = " AND ".join(where_clauses)

        sql = f"""
            SELECT c.*, d.dept_code, d.dept_name,
                   COUNT(DISTINCT co.offering_id) AS total_offerings
            FROM course c
            JOIN department d ON c.dept_id = d.dept_id
            LEFT JOIN course_offering co ON c.course_id = co.course_id
            WHERE {where_sql}
            GROUP BY c.course_id
            ORDER BY c.course_code ASC
        """
        return db_pool.execute_query(sql, tuple(params), fetch="all")

    @staticmethod
    def get_by_id(course_id):
        sql = """
            SELECT c.*, d.dept_code, d.dept_name
            FROM course c
            JOIN department d ON c.dept_id = d.dept_id
            WHERE c.course_id = %s
        """
        return db_pool.execute_query(sql, (course_id,), fetch="one")

    @staticmethod
    def create(course_code, title, credits, dept_id, semester_no):
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9_-]{1,19}", course_code) or not title.strip():
            raise ValueError("Enter a course code and title.")
        if not 1 <= credits <= 6 or not 1 <= semester_no <= 8:
            raise ValueError("Credits must be 1–6 and semester must be 1–8.")
        sql = """
            INSERT INTO course (course_code, title, credits, dept_id, semester_no)
            VALUES (%s, %s, %s, %s, %s)
        """
        params = (course_code, title, credits, dept_id, semester_no)
        return db_pool.execute_dml(sql, params)["lastrowid"]

    @staticmethod
    def get_offerings(academic_year=None, term=None):
        where_clauses = ["1=1"]
        params = []
        if academic_year:
            where_clauses.append("co.academic_year = %s")
            params.append(academic_year)
        if term:
            where_clauses.append("co.term = %s")
            params.append(term)
        where_sql = " AND ".join(where_clauses)

        sql = f"""
            SELECT co.offering_id, co.course_id, co.faculty_id, co.academic_year, co.term,
                   co.capacity, co.enrolled_count,
                   c.course_code, c.title AS course_title, c.credits,
                   d.dept_code, d.dept_name,
                   CONCAT(f.first_name, ' ', f.last_name) AS instructor_name,
                   ROUND(((co.enrolled_count * 1.0) / co.capacity) * 100, 1) AS utilization_pct,
                   CASE
                       WHEN co.enrolled_count >= co.capacity THEN 'FULL'
                       WHEN co.enrolled_count >= (co.capacity * 0.8) THEN 'ALMOST FULL'
                       ELSE 'AVAILABLE'
                   END AS seat_status
            FROM course_offering co
            JOIN course c ON co.course_id = c.course_id
            JOIN department d ON c.dept_id = d.dept_id
            JOIN faculty f ON co.faculty_id = f.faculty_id
            WHERE {where_sql}
            ORDER BY c.course_code ASC
        """
        return db_pool.execute_query(sql, tuple(params), fetch="all")

    @staticmethod
    def get_offering_by_id(offering_id):
        sql = """
            SELECT co.*, c.course_code, c.title AS course_title, c.credits,
                   d.dept_code, d.dept_name,
                   CONCAT(f.first_name, ' ', f.last_name) AS instructor_name
            FROM course_offering co
            JOIN course c ON co.course_id = c.course_id
            JOIN department d ON c.dept_id = d.dept_id
            JOIN faculty f ON co.faculty_id = f.faculty_id
            WHERE co.offering_id = %s
        """
        return db_pool.execute_query(sql, (offering_id,), fetch="one")

    @staticmethod
    def create_offering(course_id, faculty_id, academic_year, term, capacity):
        if not re.fullmatch(r"\d{4}-\d{4}", academic_year) or int(academic_year[-4:]) != int(academic_year[:4]) + 1:
            raise ValueError("Academic year must contain two consecutive years, e.g. 2026-2027.")
        if term not in ("Fall", "Spring", "Summer") or not 1 <= capacity <= 1000:
            raise ValueError("Choose a valid term and a capacity between 1 and 1,000.")
        if db_pool.execute_query("SELECT status FROM faculty WHERE faculty_id=%s", (faculty_id,), fetch="val") != "Active":
            raise ValueError("Choose an active faculty member.")
        sql = """
            INSERT INTO course_offering (course_id, faculty_id, academic_year, term, capacity, enrolled_count)
            VALUES (%s, %s, %s, %s, %s, 0)
        """
        params = (course_id, faculty_id, academic_year, term, capacity)
        return db_pool.execute_dml(sql, params)["lastrowid"]


    @staticmethod
    def get_academic_years():
        return [row["academic_year"] for row in db_pool.execute_query("SELECT DISTINCT academic_year FROM course_offering ORDER BY academic_year DESC")]
