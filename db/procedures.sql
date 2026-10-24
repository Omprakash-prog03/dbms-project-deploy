-- ============================================================================
-- STUDENT INFORMATION MANAGEMENT SYSTEM (SIMS) - STORED PROCEDURES & FUNCTIONS
-- Engine: MySQL 8.0+ | Delimiter: $$
-- Description: ACID transactions with pessimistic row-locking and business calculations.
-- ============================================================================

USE sims_db;

DELIMITER $$

-- ============================================================================
-- 1. sp_enroll_student: Atomic Enrollment with Row-Locking against Concurrency
-- ============================================================================
DROP PROCEDURE IF EXISTS sp_enroll_student$$
CREATE PROCEDURE sp_enroll_student(
    IN p_student_id INT,
    IN p_offering_id INT,
    OUT p_status_code INT,
    OUT p_message VARCHAR(255)
)
proc_label: BEGIN
    DECLARE v_capacity SMALLINT;
    DECLARE v_enrolled SMALLINT;
    DECLARE v_student_status VARCHAR(20);
    DECLARE v_existing_count INT;

    -- Exit handler for unexpected SQLEXCEPTION
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        SET p_status_code = 500;
        SET p_message = 'Database error: Transaction rolled back.';
    END;

    START TRANSACTION;

    -- Step 1: Validate student eligibility
    SELECT status INTO v_student_status
    FROM student WHERE student_id = p_student_id;

    IF v_student_status IS NULL THEN
        ROLLBACK;
        SET p_status_code = 404;
        SET p_message = 'Student record does not exist.';
        LEAVE proc_label;
    ELSEIF v_student_status != 'Active' THEN
        ROLLBACK;
        SET p_status_code = 400;
        SET p_message = CONCAT('Cannot enroll: Student status is ', v_student_status);
        LEAVE proc_label;
    END IF;

    -- Step 2: Guard against duplicate registration
    SELECT COUNT(*) INTO v_existing_count
    FROM enrollment
    WHERE student_id = p_student_id AND offering_id = p_offering_id;

    IF v_existing_count > 0 THEN
        ROLLBACK;
        SET p_status_code = 409;
        SET p_message = 'Student is already enrolled in this course offering.';
        LEAVE proc_label;
    END IF;

    -- Step 3: PESSIMISTIC ROW LOCKING - Prevents overselling race condition
    SELECT capacity, enrolled_count INTO v_capacity, v_enrolled
    FROM course_offering
    WHERE offering_id = p_offering_id
    FOR UPDATE;

    IF v_capacity IS NULL THEN
        ROLLBACK;
        SET p_status_code = 404;
        SET p_message = 'Course offering does not exist.';
        LEAVE proc_label;
    END IF;

    IF v_enrolled >= v_capacity THEN
        ROLLBACK;
        SET p_status_code = 409;
        SET p_message = 'Offering capacity is full. Zero seats remaining.';
        LEAVE proc_label;
    END IF;

    -- Step 4: Perform enrollment insertion (triggers maintain enrolled_count)
    INSERT INTO enrollment (student_id, offering_id, enroll_date, status)
    VALUES (p_student_id, p_offering_id, CURDATE(), 'Enrolled');

    COMMIT;
    SET p_status_code = 200;
    SET p_message = 'Enrollment successfully confirmed.';
END$$

-- ============================================================================
-- 2. sp_approve_admission: Multi-Table Transactional Matriculation
-- ============================================================================
DROP PROCEDURE IF EXISTS sp_approve_admission$$
CREATE PROCEDURE sp_approve_admission(
    IN p_application_id INT,
    IN p_reviewer_faculty_id INT,
    IN p_date_of_birth DATE,
    IN p_password_hash VARCHAR(255),
    OUT p_new_student_id INT,
    OUT p_generated_roll_no VARCHAR(20),
    OUT p_status_code INT,
    OUT p_message VARCHAR(255)
)
proc_label: BEGIN
    DECLARE v_app_status VARCHAR(20);
    DECLARE v_applicant_name VARCHAR(100);
    DECLARE v_email VARCHAR(100);
    DECLARE v_phone VARCHAR(20);
    DECLARE v_dept_id INT;
    DECLARE v_dept_code VARCHAR(10);
    DECLARE v_year_suffix VARCHAR(2);
    DECLARE v_seq INT;
    DECLARE v_first_name VARCHAR(50);
    DECLARE v_last_name VARCHAR(50);

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        SET p_status_code = 500;
        SET p_message = 'Transaction aborted: Failed to approve admission application.';
    END;

    START TRANSACTION;

    SELECT applicant_name, email, phone, dept_id, status
    INTO v_applicant_name, v_email, v_phone, v_dept_id, v_app_status
    FROM admission_application
    WHERE application_id = p_application_id
    FOR UPDATE;

    IF v_app_status IS NULL THEN
        ROLLBACK;
        SET p_status_code = 404;
        SET p_message = 'Admission application not found.';
        LEAVE proc_label;
    ELSEIF v_app_status != 'Pending' THEN
        ROLLBACK;
        SET p_status_code = 400;
        SET p_message = CONCAT('Application cannot be processed. Current status: ', v_app_status);
        LEAVE proc_label;
    END IF;

    IF p_date_of_birth IS NULL OR TIMESTAMPDIFF(YEAR, p_date_of_birth, CURDATE()) < 15
       OR p_password_hash IS NULL OR LENGTH(p_password_hash) != 60
       OR LEFT(p_password_hash, 4) NOT IN ('$2a$', '$2b$', '$2y$') THEN
        ROLLBACK;
        SET p_status_code = 400;
        SET p_message = 'Confirm a valid birth date and provide a fresh bcrypt password hash.';
        LEAVE proc_label;
    END IF;

    -- Parse name components
    SET v_first_name = SUBSTRING_INDEX(v_applicant_name, ' ', 1);
    IF LOCATE(' ', v_applicant_name) > 0 THEN
        SET v_last_name = SUBSTRING(v_applicant_name, LOCATE(' ', v_applicant_name) + 1);
    ELSE
        SET v_last_name = 'Scholar';
    END IF;

    -- Generate unique roll number: YY + DEPT_CODE + 3-digit sequence
    SELECT dept_code INTO v_dept_code FROM department WHERE dept_id = v_dept_id FOR UPDATE;
    SET v_year_suffix = DATE_FORMAT(CURDATE(), '%y');

    SELECT COALESCE(MAX(CAST(SUBSTRING(roll_no, LENGTH(CONCAT(v_year_suffix, v_dept_code)) + 1) AS UNSIGNED)), 0) + 1 INTO v_seq
    FROM student
    WHERE roll_no REGEXP CONCAT('^', v_year_suffix, v_dept_code, '[0-9]+$');

    SET p_generated_roll_no = CONCAT(v_year_suffix, v_dept_code, LPAD(v_seq, GREATEST(3, LENGTH(v_seq)), '0'));

    -- 1. Insert Student Record
    INSERT INTO student (
        roll_no, first_name, last_name, email, phone, dob, gender,
        address, dept_id, admission_date, current_semester, status
    ) VALUES (
        p_generated_roll_no, v_first_name, v_last_name, v_email, v_phone,
        p_date_of_birth, 'Other', '',
        v_dept_id, CURDATE(), 1, 'Active'
    );
    SET p_new_student_id = LAST_INSERT_ID();

    -- 2. Provision App User with a fresh bcrypt hash generated by the application
    INSERT INTO app_user (username, password_hash, role, student_id)
    VALUES (
        LOWER(p_generated_roll_no),
        p_password_hash,
        'student',
        p_new_student_id
    );

    -- 3. Update Application Status
    UPDATE admission_application
    SET status = 'Approved', reviewed_by = p_reviewer_faculty_id, reviewed_on = NOW()
    WHERE application_id = p_application_id;

    -- 4. Audit Log
    INSERT INTO audit_log (table_name, action, record_id, new_values, changed_by)
    VALUES (
        'admission_application', 'UPDATE', p_application_id,
        JSON_OBJECT('status', 'Approved', 'student_id', p_new_student_id, 'roll_no', p_generated_roll_no),
        CURRENT_USER()
    );

    COMMIT;
    SET p_status_code = 200;
    SET p_message = 'Admission approved. Student record and portal account created.';
END$$

-- ============================================================================
-- 3. sp_record_payment: Financial Integrity & Overpayment Protection
-- ============================================================================
DROP PROCEDURE IF EXISTS sp_record_payment$$
CREATE PROCEDURE sp_record_payment(
    IN p_student_id INT,
    IN p_semester_no TINYINT,
    IN p_amount DECIMAL(10,2),
    IN p_mode VARCHAR(20),
    IN p_receipt_no VARCHAR(50),
    OUT p_status_code INT,
    OUT p_message VARCHAR(255)
)
proc_label: BEGIN
    DECLARE v_dept_id INT;
    DECLARE v_sem_fee DECIMAL(10,2);
    DECLARE v_already_paid DECIMAL(10,2);
    DECLARE v_max_payable DECIMAL(10,2);

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        SET p_status_code = 500;
        SET p_message = 'Payment recording failed: Database rolled back.';
    END;

    START TRANSACTION;

    -- Lookup student department
    SELECT dept_id INTO v_dept_id FROM student WHERE student_id = p_student_id FOR UPDATE;
    IF v_dept_id IS NULL THEN
        ROLLBACK;
        SET p_status_code = 404;
        SET p_message = 'Student does not exist.';
        LEAVE proc_label;
    END IF;

    -- Lookup fee structure
    SELECT amount INTO v_sem_fee
    FROM fee_structure
    WHERE dept_id = v_dept_id AND semester_no = p_semester_no FOR UPDATE;

    IF v_sem_fee IS NULL THEN
        ROLLBACK;
        SET p_status_code = 404;
        SET p_message = 'Fee structure not configured for this semester.';
        LEAVE proc_label;
    END IF;

    -- Calculate current paid balance
    SELECT COALESCE(SUM(amount), 0) INTO v_already_paid
    FROM fee_payment
    WHERE student_id = p_student_id AND semester_no = p_semester_no
    FOR UPDATE;

    SET v_max_payable = v_sem_fee - v_already_paid;

    IF p_amount <= 0 THEN
        ROLLBACK;
        SET p_status_code = 400;
        SET p_message = 'Payment amount must be greater than zero.';
        LEAVE proc_label;
    ELSEIF p_amount > v_max_payable THEN
        ROLLBACK;
        SET p_status_code = 400;
        SET p_message = CONCAT('Overpayment rejected. Maximum remaining fee payable: ', v_max_payable);
        LEAVE proc_label;
    END IF;

    -- Insert payment record
    INSERT INTO fee_payment (student_id, semester_no, amount, paid_on, mode, receipt_no)
    VALUES (p_student_id, p_semester_no, p_amount, CURDATE(), p_mode, p_receipt_no);

    COMMIT;
    SET p_status_code = 200;
    SET p_message = 'Payment successfully recorded.';
END$$

-- ============================================================================
-- 4. Stored Function: fn_grade (Percentage -> Letter Grade)
-- ============================================================================
DROP FUNCTION IF EXISTS fn_grade$$
CREATE FUNCTION fn_grade(p_percentage DECIMAL(5,2))
RETURNS VARCHAR(3)
DETERMINISTIC
BEGIN
    IF p_percentage IS NULL THEN RETURN NULL;
    ELSEIF p_percentage >= 90.0 THEN RETURN 'A+';
    ELSEIF p_percentage >= 80.0 THEN RETURN 'A';
    ELSEIF p_percentage >= 70.0 THEN RETURN 'B+';
    ELSEIF p_percentage >= 60.0 THEN RETURN 'B';
    ELSEIF p_percentage >= 50.0 THEN RETURN 'C';
    ELSEIF p_percentage >= 40.0 THEN RETURN 'P';
    ELSE RETURN 'F';
    END IF;
END$$

-- ============================================================================
-- 5. Stored Function: fn_attendance_pct (Enrollment -> Attendance Percentage)
-- ============================================================================
DROP FUNCTION IF EXISTS fn_attendance_pct$$
CREATE FUNCTION fn_attendance_pct(p_enrollment_id INT)
RETURNS DECIMAL(5,2)
READS SQL DATA
BEGIN
    DECLARE v_total INT;
    DECLARE v_attended INT;

    SELECT COUNT(*), SUM(CASE WHEN status IN ('Present', 'Late') THEN 1 ELSE 0 END)
    INTO v_total, v_attended
    FROM attendance
    WHERE enrollment_id = p_enrollment_id;

    IF v_total = 0 OR v_total IS NULL THEN
        RETURN 0.00;
    END IF;

    RETURN ROUND((v_attended / v_total) * 100, 2);
END$$

-- ============================================================================
-- 6. Stored Function: fn_student_cgpa (Student ID -> Cumulative Grade Point Average)
-- ============================================================================
DROP FUNCTION IF EXISTS fn_student_cgpa$$
CREATE FUNCTION fn_student_cgpa(p_student_id INT)
RETURNS DECIMAL(4,2)
READS SQL DATA
BEGIN
    DECLARE v_cgpa DECIMAL(4,2);

    SELECT ROUND(SUM(credits * CASE
        WHEN percentage >= 90 THEN 10 WHEN percentage >= 80 THEN 9
        WHEN percentage >= 70 THEN 8 WHEN percentage >= 60 THEN 7
        WHEN percentage >= 50 THEN 6 WHEN percentage >= 40 THEN 5 ELSE 0 END)
        / NULLIF(SUM(credits), 0), 2) INTO v_cgpa
    FROM (
        SELECT c.credits, 100.0 * SUM(r.marks_obtained) / SUM(ex.max_marks) AS percentage
        FROM enrollment e
        JOIN course_offering co ON co.offering_id=e.offering_id
        JOIN course c ON c.course_id=co.course_id
        JOIN result r ON r.enrollment_id=e.enrollment_id
        JOIN exam ex ON ex.exam_id=r.exam_id AND ex.offering_id=e.offering_id
        WHERE e.student_id=p_student_id AND e.status!='Dropped'
        GROUP BY e.enrollment_id,c.credits
    ) graded;

    RETURN COALESCE(v_cgpa, 0.00);
END$$

DELIMITER ;
