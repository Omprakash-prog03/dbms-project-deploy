from repositories.db_pool import db_pool
import math
from datetime import date
from decimal import Decimal
from repositories.validation import money

class ResultRepository:
    @staticmethod
    def get_exams_by_offering(offering_id):
        sql = """
            SELECT ex.*,
                   COUNT(r.result_id) AS graded_students_count,
                   ROUND(AVG(r.marks_obtained), 2) AS avg_marks
            FROM exam ex
            LEFT JOIN result r ON ex.exam_id = r.exam_id
            WHERE ex.offering_id = %s
            GROUP BY ex.exam_id
            ORDER BY ex.exam_date ASC
        """
        return db_pool.execute_query(sql, (offering_id,), fetch="all")

    @staticmethod
    def get_exam_by_id(exam_id):
        sql = """
            SELECT ex.*, co.offering_id, c.course_code, c.title AS course_title
            FROM exam ex
            JOIN course_offering co ON ex.offering_id = co.offering_id
            JOIN course c ON co.course_id = c.course_id
            WHERE ex.exam_id = %s
        """
        return db_pool.execute_query(sql, (exam_id,), fetch="one")

    @staticmethod
    def create_exam(offering_id, exam_type, max_marks, exam_date):
        if exam_type not in ('Internal', 'Midterm', 'Final'):
            raise ValueError('Choose Internal, Midterm, or Final.')
        marks = money(max_marks)
        if marks > Decimal('999.99'):
            raise ValueError('Maximum marks cannot exceed 999.99.')
        exam_date = date.fromisoformat(exam_date).isoformat()
        max_marks = float(marks)
        if db_pool.execute_query('SELECT exam_id FROM exam WHERE offering_id=%s AND exam_type=%s', (offering_id, exam_type), fetch='one'):
            raise ValueError('This exam type already exists for the selected offering.')
        sql = """
            INSERT INTO exam (offering_id, exam_type, max_marks, exam_date)
            VALUES (%s, %s, %s, %s)
        """
        return db_pool.execute_dml(sql, (offering_id, exam_type, max_marks, exam_date))["lastrowid"]

    @staticmethod
    def get_gradebook_for_exam(exam_id):
        sql = """
            SELECT
                e.enrollment_id,
                s.student_id,
                s.roll_no,
                CONCAT(s.first_name, ' ', s.last_name) AS student_name,
                d.dept_code,
                r.result_id,
                r.marks_obtained,
                ex.max_marks,
                ROUND((1.0 * r.marks_obtained / ex.max_marks) * 100, 1) AS percentage,
                fn_grade(ROUND((1.0 * r.marks_obtained / ex.max_marks) * 100, 1)) AS grade
            FROM exam ex
            JOIN course_offering co ON ex.offering_id = co.offering_id
            JOIN enrollment e ON co.offering_id = e.offering_id AND e.status = 'Enrolled'
            JOIN student s ON e.student_id = s.student_id
            JOIN department d ON s.dept_id = d.dept_id
            LEFT JOIN result r ON ex.exam_id = r.exam_id AND e.enrollment_id = r.enrollment_id
            WHERE ex.exam_id = %s
            ORDER BY s.roll_no ASC
        """
        return db_pool.execute_query(sql, (exam_id,), fetch="all")

    @staticmethod
    def save_result(exam_id, enrollment_id, marks_obtained):
        """
        Saves individual evaluation mark.
        Enforces marks_obtained <= max_marks (backed by trg_result_before_insert).
        """
        marks_obtained = float(marks_obtained)
        if not math.isfinite(marks_obtained):
            raise ValueError("Marks must be a finite number.")
        exam = ResultRepository.get_exam_by_id(exam_id)
        if not exam:
            raise ValueError("Exam does not exist.")
        if float(marks_obtained) > float(exam["max_marks"]):
            raise ValueError(f"Integrity violation: marks_obtained ({marks_obtained}) cannot exceed exam max_marks ({exam['max_marks']}).")
        if float(marks_obtained) < 0:
            raise ValueError("Marks obtained cannot be negative.")

        enrollment = db_pool.execute_query("SELECT offering_id, status FROM enrollment WHERE enrollment_id = %s", (enrollment_id,), fetch="one")
        if not enrollment or enrollment["offering_id"] != exam["offering_id"] or enrollment["status"] != "Enrolled":
            raise ValueError("The student must be actively enrolled in this exam's course offering.")
        # Atomic upsert avoids duplicate inserts from double clicks/concurrent saves.
        sql = "INSERT INTO result (exam_id, enrollment_id, marks_obtained) VALUES (%s, %s, %s) "
        sql += "ON DUPLICATE KEY UPDATE marks_obtained = VALUES(marks_obtained)" if db_pool.is_mysql else "ON CONFLICT(exam_id, enrollment_id) DO UPDATE SET marks_obtained = excluded.marks_obtained"
        db_pool.execute_dml(sql, (exam_id, enrollment_id, marks_obtained))
        return db_pool.execute_query("SELECT result_id FROM result WHERE exam_id=%s AND enrollment_id=%s", (exam_id, enrollment_id), fetch="val")
