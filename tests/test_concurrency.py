import random
import threading
import pytest
from repositories.db_pool import db_pool
from repositories.enrollments import EnrollmentRepository

class TestConcurrency:

    def test_two_threads_last_seat_race_condition(self):
        """
        Concurrency test:
        Create an offering with capacity = 1 and enrolled_count = 0.
        Launch 2 concurrent threads trying to enroll two distinct students at once.
        Assert that EXACTLY ONE thread succeeds (200), and the other fails (409 or error).
        Assert final enrolled_count == 1, NEVER 2!
        """
        rand_yr = f"20{random.randint(70, 79)}-20{random.randint(70, 79)}"
        off_res = db_pool.execute_dml(
            "INSERT INTO course_offering (course_id, faculty_id, academic_year, term, capacity, enrolled_count) "
            "VALUES (1, 1, %s, 'Fall', 1, 0)",
            (rand_yr,)
        )
        off_id = off_res["lastrowid"]

        # Fetch 2 distinct active students
        stu_rows = db_pool.execute_query("SELECT student_id FROM student WHERE status = 'Active' LIMIT 2", fetch="all")
        s1 = stu_rows[0]["student_id"]
        s2 = stu_rows[1]["student_id"]

        results = []

        def worker(student_id):
            res = EnrollmentRepository.enroll_student(student_id, off_id)
            results.append(res)

        t1 = threading.Thread(target=worker, args=(s1,))
        t2 = threading.Thread(target=worker, args=(s2,))

        # Launch simultaneously
        t1.start()
        t2.start()

        t1.join()
        t2.join()

        try:
            assert len(results) == 2
            success_count = sum(1 for r in results if r["status_code"] == 200)
            fail_count = sum(1 for r in results if r["status_code"] != 200)

            # Exactly one must succeed, exactly one must fail
            assert success_count == 1, f"Expected exactly 1 success, got {success_count}. Results: {results}"
            assert fail_count == 1, f"Expected exactly 1 failure, got {fail_count}. Results: {results}"

            # Verify physical enrolled_count in database is exactly 1 (no overselling!)
            final_count = db_pool.execute_query(
                "SELECT enrolled_count FROM course_offering WHERE offering_id = %s",
                (off_id,), fetch="val"
            )
            assert final_count == 1, f"Physical capacity breached! enrolled_count = {final_count}"
        finally:
            db_pool.execute_dml("DELETE FROM enrollment WHERE offering_id = %s", (off_id,))
            db_pool.execute_dml("DELETE FROM course_offering WHERE offering_id = %s", (off_id,))
