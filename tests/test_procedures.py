import pytest
import random
from repositories.db_pool import db_pool
from repositories.enrollments import EnrollmentRepository
from repositories.fees import FeeRepository
from repositories.admissions import AdmissionsRepository

class TestStoredProcedures:

    def test_sp_enroll_student_success_and_duplicate(self):
        """Rule: sp_enroll_student confirms enrollment, then rejects duplicate."""
        rand_yr = f"20{random.randint(90, 99)}-20{random.randint(90, 99)}"
        off_res = db_pool.execute_dml(
            "INSERT INTO course_offering (course_id, faculty_id, academic_year, term, capacity, enrolled_count) "
            "VALUES (1, 1, %s, 'Fall', 5, 0)",
            (rand_yr,)
        )
        off_id = off_res["lastrowid"]
        stu_id = db_pool.execute_query("SELECT student_id FROM student WHERE status = 'Active' LIMIT 1", fetch="val")

        try:
            # 1. First enrollment succeeds
            res1 = EnrollmentRepository.enroll_student(stu_id, off_id)
            assert res1["status_code"] == 200
            assert "confirmed" in res1["message"].lower()

            # 2. Duplicate enrollment rejected
            res2 = EnrollmentRepository.enroll_student(stu_id, off_id)
            assert res2["status_code"] == 409
            assert "already enrolled" in res2["message"].lower()
        finally:
            db_pool.execute_dml("DELETE FROM enrollment WHERE offering_id = %s", (off_id,))
            db_pool.execute_dml("DELETE FROM course_offering WHERE offering_id = %s", (off_id,))

    def test_sp_enroll_student_inactive_rejected(self):
        """Rule: sp_enroll_student rejects registration if student is not Active."""
        # Create a suspended student
        res_stu = db_pool.execute_dml(
            "INSERT INTO student (roll_no, first_name, last_name, email, phone, dob, gender, address, dept_id, admission_date, current_semester, status) "
            "VALUES ('99SUSP01', 'Suspended', 'Student', 'susp@sims.edu', '9999999999', '2004-01-01', 'Other', 'Campus', 1, '2026-06-01', 1, 'Suspended')"
        )
        susp_id = res_stu["lastrowid"]
        off_id = db_pool.execute_query("SELECT offering_id FROM course_offering LIMIT 1", fetch="val")

        try:
            res = EnrollmentRepository.enroll_student(susp_id, off_id)
            assert res["status_code"] == 400
            assert "cannot enroll" in res["message"].lower()
        finally:
            db_pool.execute_dml("DELETE FROM student WHERE student_id = %s", (susp_id,))

    def test_sp_record_payment_overpayment_rejected(self):
        """Rule: sp_record_payment rejects payment exceeding semester fee balance."""
        stu = db_pool.execute_query("SELECT student_id, dept_id, current_semester FROM student WHERE status = 'Active' LIMIT 1", fetch="one")
        s_id = stu["student_id"]
        sem = stu["current_semester"]

        # Fee structure amount
        fee = db_pool.execute_query("SELECT amount FROM fee_structure WHERE dept_id = %s AND semester_no = %s", (stu["dept_id"], sem), fetch="val")
        assert fee is not None

        # Attempt to pay an absurdly large amount (overpayment)
        res = FeeRepository.record_payment(s_id, sem, float(fee) * 5.0, "Card", f"REC-OVERPAY-{random.randint(1000,9999)}")
        assert res["status_code"] == 400
        assert "overpayment" in res["message"].lower()

    def test_sp_approve_admission_atomicity_and_rollback(self):
        """
        Rule: sp_approve_admission must be atomic.
        If an error occurs mid-way (e.g. invalid reviewer or state violation),
        nothing is committed into student or app_user.
        """
        # Create a pending application
        app_id = AdmissionsRepository.create_application("Atomic Test Applicant", "atomic.test@gmail.com", "9876543210", 1)

        # Check initial counts
        stu_count_before = db_pool.execute_query("SELECT COUNT(*) FROM student", fetch="val")

        # Call with already approved or invalid status to trigger error
        db_pool.execute_dml("UPDATE admission_application SET status = 'Rejected' WHERE application_id = %s", (app_id,))

        res = AdmissionsRepository.approve_admission(app_id, reviewer_id=1)
        assert res["status_code"] == 400

        # Assert zero new student records created
        stu_count_after = db_pool.execute_query("SELECT COUNT(*) FROM student", fetch="val")
        assert stu_count_before == stu_count_after

        # Clean up application
        db_pool.execute_dml("DELETE FROM admission_application WHERE application_id = %s", (app_id,))
