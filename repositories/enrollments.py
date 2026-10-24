from repositories.db_pool import db_pool
import datetime

class EnrollmentRepository:
    @staticmethod
    def enroll_student(student_id, offering_id):
        """
        Executes atomic enrollment with pessimistic validation.
        Invokes sp_enroll_student on MySQL or the atomic transactional procedure logic.
        """
        if db_pool.is_mysql:
            with db_pool.get_connection() as conn:
                cur = conn.cursor()
                try:
                    cur.callproc("sp_enroll_student", (student_id, offering_id, 0, ""))
                    cur.execute("SELECT @_sp_enroll_student_2, @_sp_enroll_student_3")
                    res = cur.fetchone()
                    status_code = res.get("@_sp_enroll_student_2", 200) if isinstance(res, dict) else res[0]
                    message = res.get("@_sp_enroll_student_3", "Enrolled") if isinstance(res, dict) else res[1]
                    return {"status_code": status_code, "message": message}
                finally:
                    cur.close()
        else:
            # Atomic transaction block matching sp_enroll_student
            with db_pool.get_connection() as conn:
                cur = conn.cursor()
                try:
                    cur.execute("BEGIN IMMEDIATE TRANSACTION;")

                    # 1. Student check
                    cur.execute("SELECT status FROM student WHERE student_id = ?", (student_id,))
                    stu = cur.fetchone()
                    if not stu:
                        conn.rollback()
                        return {"status_code": 404, "message": "Student record does not exist."}
                    if stu[0] != "Active":
                        conn.rollback()
                        return {"status_code": 400, "message": f"Cannot enroll: Student status is {stu[0]}."}

                    # 2. Duplicate check
                    cur.execute("SELECT COUNT(*) FROM enrollment WHERE student_id = ? AND offering_id = ?", (student_id, offering_id))
                    if cur.fetchone()[0] > 0:
                        conn.rollback()
                        return {"status_code": 409, "message": "Student is already enrolled in this course offering."}

                    # 3. Capacity lock & check
                    cur.execute("SELECT capacity, enrolled_count FROM course_offering WHERE offering_id = ?", (offering_id,))
                    off = cur.fetchone()
                    if not off:
                        conn.rollback()
                        return {"status_code": 404, "message": "Course offering does not exist."}
                    capacity, enrolled_count = off[0], off[1]
                    if enrolled_count >= capacity:
                        conn.rollback()
                        return {"status_code": 409, "message": "Offering capacity is full. Zero seats remaining."}

                    # 4. Insert enrollment (Trigger maintains enrolled_count)
                    cur.execute(
                        "INSERT INTO enrollment (student_id, offering_id, enroll_date, status) VALUES (?, ?, ?, 'Enrolled')",
                        (student_id, offering_id, datetime.date.today().isoformat())
                    )
                    conn.commit()
                    return {"status_code": 200, "message": "Enrollment successfully confirmed."}
                except Exception as e:
                    conn.rollback()
                    return {"status_code": 500, "message": f"Transaction rolled back: {str(e)}"}
                finally:
                    cur.close()

    @staticmethod
    def get_all(offering_id=None, student_id=None):
        where_clauses = ["1=1"]
        params = []
        if offering_id:
            where_clauses.append("e.offering_id = %s")
            params.append(offering_id)
        if student_id:
            where_clauses.append("e.student_id = %s")
            params.append(student_id)
        where_sql = " AND ".join(where_clauses)

        sql = f"""
            SELECT e.*, s.roll_no,
                   CONCAT(s.first_name, ' ', s.last_name) AS student_name,
                   d.dept_code,
                   c.course_code, c.title AS course_title,
                   co.academic_year, co.term
            FROM enrollment e
            JOIN student s ON e.student_id = s.student_id
            JOIN department d ON s.dept_id = d.dept_id
            JOIN course_offering co ON e.offering_id = co.offering_id
            JOIN course c ON co.course_id = c.course_id
            WHERE {where_sql}
            ORDER BY e.enroll_date DESC
        """
        return db_pool.execute_query(sql, tuple(params), fetch="all")
