import pytest
from repositories.db_pool import db_pool

class TestSchemaConstraints:

    def test_uk_student_roll_duplicate_rejected(self):
        """Rule: roll_no must be globally UNIQUE."""
        # Query an existing roll_no
        existing_roll = db_pool.execute_query("SELECT roll_no FROM student LIMIT 1", fetch="val")
        assert existing_roll is not None

        # Attempt to insert second student with same roll number
        with pytest.raises(Exception):
            db_pool.execute_dml(
                "INSERT INTO student (roll_no, first_name, last_name, email, phone, dob, gender, address, dept_id, admission_date, current_semester, status) "
                "VALUES (%s, 'Duplicate', 'Student', 'unique_dup@sims.edu', '9999999999', '2004-01-01', 'Other', 'Test Address', 1, '2026-06-01', 1, 'Active')",
                (existing_roll,)
            )

    def test_uk_student_email_duplicate_rejected(self):
        """Rule: email must be globally UNIQUE."""
        existing_email = db_pool.execute_query("SELECT email FROM student LIMIT 1", fetch="val")
        assert existing_email is not None

        with pytest.raises(Exception):
            db_pool.execute_dml(
                "INSERT INTO student (roll_no, first_name, last_name, email, phone, dob, gender, address, dept_id, admission_date, current_semester, status) "
                "VALUES ('99UNIQUE01', 'Duplicate', 'Email', %s, '9999999999', '2004-01-01', 'Other', 'Test Address', 1, '2026-06-01', 1, 'Active')",
                (existing_email,)
            )

    def test_chk_course_credits_range_rejected(self):
        """Rule: credits must be BETWEEN 1 AND 6."""
        with pytest.raises(Exception):
            db_pool.execute_dml(
                "INSERT INTO course (course_code, title, credits, dept_id, semester_no) VALUES ('BAD99', 'Invalid High Credit', 10, 1, 1)"
            )

    def test_chk_faculty_salary_positive_rejected(self):
        """Rule: faculty salary must be > 0."""
        with pytest.raises(Exception):
            db_pool.execute_dml(
                "INSERT INTO faculty (first_name, last_name, email, phone, dept_id, designation, hire_date, salary, status) "
                "VALUES ('Negative', 'Salary', 'neg.sal@sims.edu', '9999999999', 1, 'Lecturer', '2025-01-01', -500.0, 'Active')"
            )

    def test_not_null_violation_rejected(self):
        """Rule: first_name is NOT NULL."""
        with pytest.raises(Exception):
            db_pool.execute_dml(
                "INSERT INTO student (roll_no, first_name, last_name, email, phone, dob, gender, address, dept_id, admission_date, current_semester, status) "
                "VALUES ('99NULL01', NULL, 'NoFirst', 'null.first@sims.edu', '9999999999', '2004-01-01', 'Other', 'Test Address', 1, '2026-06-01', 1, 'Active')"
            )

    def test_fk_restrict_dept_delete_with_students(self):
        """Rule: ON DELETE RESTRICT on department prevents orphan students."""
        dept_with_students = db_pool.execute_query("SELECT dept_id FROM student LIMIT 1", fetch="val")
        assert dept_with_students is not None

        with pytest.raises(Exception):
            db_pool.execute_dml("DELETE FROM department WHERE dept_id = %s", (dept_with_students,))
