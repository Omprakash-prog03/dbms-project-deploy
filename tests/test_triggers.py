import random
import pytest
from repositories.db_pool import db_pool
from repositories.results import ResultRepository

class TestTriggers:

    def test_trg_capacity_limit_rejection(self):
        """Rule: Course offering cannot exceed physical capacity."""
        # Use a dynamic random academic year to avoid unique constraint collision
        rand_yr = f"20{random.randint(60, 89)}-20{random.randint(60, 89)}"
        res = db_pool.execute_dml(
            "INSERT INTO course_offering (course_id, faculty_id, academic_year, term, capacity, enrolled_count) "
            "VALUES (1, 1, %s, 'Fall', 1, 0)",
            (rand_yr,)
        )
        off_id = res["lastrowid"]

        try:
            # First enrollment succeeds
            stu_ids = db_pool.execute_query("SELECT student_id FROM student WHERE status = 'Active' LIMIT 2", fetch="all")
            s1 = stu_ids[0]["student_id"]
            s2 = stu_ids[1]["student_id"]

            db_pool.execute_dml(
                "INSERT INTO enrollment (student_id, offering_id, enroll_date, status) VALUES (%s, %s, '2029-08-01', 'Enrolled')",
                (s1, off_id)
            )

            # Second enrollment into full offering MUST BE REJECTED by trigger
            with pytest.raises(Exception) as exc_info:
                db_pool.execute_dml(
                    "INSERT INTO enrollment (student_id, offering_id, enroll_date, status) VALUES (%s, %s, '2029-08-01', 'Enrolled')",
                    (s2, off_id)
                )
            assert "capacity" in str(exc_info.value).lower()
        finally:
            # Cleanup
            db_pool.execute_dml("DELETE FROM enrollment WHERE offering_id = %s", (off_id,))
            db_pool.execute_dml("DELETE FROM course_offering WHERE offering_id = %s", (off_id,))

    def test_trg_enrolled_count_synchronizer(self):
        """Rule: enrolled_count increments on insert, decrements on drop and delete."""
        rand_yr = f"20{random.randint(40, 59)}-20{random.randint(40, 59)}"
        res = db_pool.execute_dml(
            "INSERT INTO course_offering (course_id, faculty_id, academic_year, term, capacity, enrolled_count) "
            "VALUES (1, 1, %s, 'Spring', 10, 0)",
            (rand_yr,)
        )
        off_id = res["lastrowid"]

        try:
            # Initially 0
            c0 = db_pool.execute_query("SELECT enrolled_count FROM course_offering WHERE offering_id = %s", (off_id,), fetch="val")
            assert c0 == 0

            # Insert 1 enrollment
            stu_id = db_pool.execute_query("SELECT student_id FROM student WHERE status = 'Active' LIMIT 1", fetch="val")
            enr_res = db_pool.execute_dml(
                "INSERT INTO enrollment (student_id, offering_id, enroll_date, status) VALUES (%s, %s, '2031-01-10', 'Enrolled')",
                (stu_id, off_id)
            )
            enr_id = enr_res["lastrowid"]

            # Must be 1
            c1 = db_pool.execute_query("SELECT enrolled_count FROM course_offering WHERE offering_id = %s", (off_id,), fetch="val")
            assert c1 == 1

            # Drop enrollment -> Must become 0
            db_pool.execute_dml("UPDATE enrollment SET status = 'Dropped' WHERE enrollment_id = %s", (enr_id,))
            c2 = db_pool.execute_query("SELECT enrolled_count FROM course_offering WHERE offering_id = %s", (off_id,), fetch="val")
            assert c2 == 0

            # Re-enroll -> Must become 1
            db_pool.execute_dml("UPDATE enrollment SET status = 'Enrolled' WHERE enrollment_id = %s", (enr_id,))
            c3 = db_pool.execute_query("SELECT enrolled_count FROM course_offering WHERE offering_id = %s", (off_id,), fetch="val")
            assert c3 == 1

            # Delete -> Must become 0
            db_pool.execute_dml("DELETE FROM enrollment WHERE enrollment_id = %s", (enr_id,))
            c4 = db_pool.execute_query("SELECT enrolled_count FROM course_offering WHERE offering_id = %s", (off_id,), fetch="val")
            assert c4 == 0
        finally:
            db_pool.execute_dml("DELETE FROM enrollment WHERE offering_id = %s", (off_id,))
            db_pool.execute_dml("DELETE FROM course_offering WHERE offering_id = %s", (off_id,))

    def test_trg_marks_ceiling_rejection(self):
        """Rule: marks_obtained cannot exceed exam.max_marks."""
        ex = db_pool.execute_query("SELECT exam_id, max_marks FROM exam WHERE max_marks = 30.0 LIMIT 1", fetch="one")
        if not ex:
            ex_res = db_pool.execute_dml("INSERT INTO exam (offering_id, exam_type, max_marks, exam_date) VALUES (1, 'Internal', 30.0, '2026-05-01')")
            exam_id = ex_res["lastrowid"]
            max_m = 30.0
        else:
            exam_id = ex["exam_id"]
            max_m = ex["max_marks"]

        enr_id = db_pool.execute_query("SELECT enrollment_id FROM enrollment LIMIT 1", fetch="val")

        with pytest.raises(Exception) as exc_info:
            ResultRepository.save_result(exam_id, enr_id, max_m + 10.0)
        assert "exceed" in str(exc_info.value).lower()

    def test_trg_audit_logging_on_student_update(self):
        """Rule: Student status modification writes JSON audit ledger entry."""
        stu = db_pool.execute_query("SELECT student_id, status FROM student WHERE status = 'Active' LIMIT 1", fetch="one")
        s_id = stu["student_id"]

        db_pool.execute_dml("UPDATE student SET status = 'Suspended' WHERE student_id = %s", (s_id,))

        log_row = db_pool.execute_query(
            "SELECT * FROM audit_log WHERE table_name = 'student' AND record_id = %s ORDER BY log_id DESC LIMIT 1",
            (s_id,), fetch="one"
        )
        assert log_row is not None
        # Revert
        db_pool.execute_dml("UPDATE student SET status = 'Active' WHERE student_id = %s", (s_id,))
