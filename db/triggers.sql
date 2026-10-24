-- ============================================================================
-- STUDENT INFORMATION MANAGEMENT SYSTEM (SIMS) - DATABASE TRIGGERS
-- Engine: MySQL 8.0+ | Delimiter: $$
-- Description: Automated business rule enforcement and autonomous auditing.
-- ============================================================================

USE sims_db;

DELIMITER $$

-- 1. Guard against full offering and inactive student registration
DROP TRIGGER IF EXISTS trg_enrollment_before_insert$$
CREATE TRIGGER trg_enrollment_before_insert
BEFORE INSERT ON enrollment
FOR EACH ROW
BEGIN
    DECLARE v_capacity SMALLINT;
    DECLARE v_enrolled SMALLINT;
    DECLARE v_student_status VARCHAR(20);

    -- Check student active status
    SELECT status INTO v_student_status
    FROM student WHERE student_id = NEW.student_id;

    IF NEW.status = 'Enrolled' AND v_student_status != 'Active' THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Registration rejected: Student profile is not Active.';
    END IF;

    -- Check offering capacity
    SELECT capacity, enrolled_count INTO v_capacity, v_enrolled
    FROM course_offering WHERE offering_id = NEW.offering_id;

    IF NEW.status = 'Enrolled' AND v_enrolled >= v_capacity THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Registration rejected: Course offering has reached maximum seating capacity.';
    END IF;
END$$

-- 2. Synchronize enrolled_count on new enrollment
DROP TRIGGER IF EXISTS trg_enrollment_after_insert$$
CREATE TRIGGER trg_enrollment_after_insert
AFTER INSERT ON enrollment
FOR EACH ROW
BEGIN
    IF NEW.status = 'Enrolled' THEN
        UPDATE course_offering
        SET enrolled_count = enrolled_count + 1
        WHERE offering_id = NEW.offering_id;
    END IF;
END$$

-- 3. Synchronize enrolled_count on status change (e.g. Enrolled <-> Dropped)
DROP TRIGGER IF EXISTS trg_enrollment_after_update$$
CREATE TRIGGER trg_enrollment_after_update
AFTER UPDATE ON enrollment
FOR EACH ROW
BEGIN
    IF OLD.status = 'Enrolled' THEN
        UPDATE course_offering
        SET enrolled_count = GREATEST(0, enrolled_count - 1)
        WHERE offering_id = OLD.offering_id;
    END IF;
    IF NEW.status = 'Enrolled' THEN
        UPDATE course_offering
        SET enrolled_count = enrolled_count + 1
        WHERE offering_id = NEW.offering_id;
    END IF;
END$$

-- 4. Synchronize enrolled_count on record deletion
DROP TRIGGER IF EXISTS trg_enrollment_after_delete$$
CREATE TRIGGER trg_enrollment_after_delete
AFTER DELETE ON enrollment
FOR EACH ROW
BEGIN
    IF OLD.status = 'Enrolled' THEN
        UPDATE course_offering
        SET enrolled_count = GREATEST(0, enrolled_count - 1)
        WHERE offering_id = OLD.offering_id;
    END IF;
END$$

-- 5. Enforce exam maximum marks ceiling on result entry
DROP TRIGGER IF EXISTS trg_result_before_insert$$
CREATE TRIGGER trg_result_before_insert
BEFORE INSERT ON result
FOR EACH ROW
BEGIN
    DECLARE v_max DECIMAL(5,2);
    SELECT max_marks INTO v_max FROM exam WHERE exam_id = NEW.exam_id;
    IF NEW.marks_obtained > v_max THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Integrity violation: marks_obtained cannot exceed exam max_marks.';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM enrollment e JOIN exam ex ON e.offering_id=ex.offering_id
                   WHERE e.enrollment_id=NEW.enrollment_id AND ex.exam_id=NEW.exam_id AND e.status='Enrolled') THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Result must match an active enrollment in this exam offering.';
    END IF;
END$$

-- 6. Enforce exam maximum marks ceiling on result update
DROP TRIGGER IF EXISTS trg_result_before_update$$
CREATE TRIGGER trg_result_before_update
BEFORE UPDATE ON result
FOR EACH ROW
BEGIN
    DECLARE v_max DECIMAL(5,2);
    SELECT max_marks INTO v_max FROM exam WHERE exam_id = NEW.exam_id;
    IF NEW.marks_obtained > v_max THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Integrity violation: marks_obtained cannot exceed exam max_marks.';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM enrollment e JOIN exam ex ON e.offering_id=ex.offering_id
                   WHERE e.enrollment_id=NEW.enrollment_id AND ex.exam_id=NEW.exam_id AND e.status='Enrolled') THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Result must match an active enrollment in this exam offering.';
    END IF;
END$$

-- 7. Reject attendance marking for dropped enrollments
DROP TRIGGER IF EXISTS trg_attendance_before_insert$$
CREATE TRIGGER trg_attendance_before_insert
BEFORE INSERT ON attendance
FOR EACH ROW
BEGIN
    DECLARE v_enr_status VARCHAR(20);
    SELECT status INTO v_enr_status FROM enrollment WHERE enrollment_id = NEW.enrollment_id;
    IF v_enr_status IS NULL OR v_enr_status != 'Enrolled' THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Attendance requires an active enrollment.';
    END IF;
END$$

-- 8. Audit log triggers on student updates
DROP TRIGGER IF EXISTS trg_student_after_update$$
CREATE TRIGGER trg_student_after_update
AFTER UPDATE ON student
FOR EACH ROW
BEGIN
    INSERT INTO audit_log (table_name, action, record_id, old_values, new_values, changed_by)
    VALUES (
        'student',
        'UPDATE',
        NEW.student_id,
        JSON_OBJECT('status', OLD.status, 'current_semester', OLD.current_semester, 'email', OLD.email),
        JSON_OBJECT('status', NEW.status, 'current_semester', NEW.current_semester, 'email', NEW.email),
        CURRENT_USER()
    );
END$$

-- 9. Audit log triggers on student deletions
DROP TRIGGER IF EXISTS trg_student_after_delete$$
CREATE TRIGGER trg_student_after_delete
AFTER DELETE ON student
FOR EACH ROW
BEGIN
    INSERT INTO audit_log (table_name, action, record_id, old_values, new_values, changed_by)
    VALUES (
        'student',
        'DELETE',
        OLD.student_id,
        JSON_OBJECT('roll_no', OLD.roll_no, 'name', CONCAT(OLD.first_name, ' ', OLD.last_name)),
        NULL,
        CURRENT_USER()
    );
END$$

-- 10. Audit log trigger on fee payment transactions
DROP TRIGGER IF EXISTS trg_fee_payment_after_insert$$
CREATE TRIGGER trg_fee_payment_after_insert
AFTER INSERT ON fee_payment
FOR EACH ROW
BEGIN
    INSERT INTO audit_log (table_name, action, record_id, old_values, new_values, changed_by)
    VALUES (
        'fee_payment',
        'INSERT',
        NEW.payment_id,
        NULL,
        JSON_OBJECT('student_id', NEW.student_id, 'semester', NEW.semester_no, 'amount', NEW.amount, 'receipt', NEW.receipt_no),
        CURRENT_USER()
    );
END$$


-- Additional update guards ensure edits cannot bypass insert-only constraints.
DROP TRIGGER IF EXISTS trg_enrollment_before_update$$
CREATE TRIGGER trg_enrollment_before_update BEFORE UPDATE ON enrollment FOR EACH ROW
BEGIN
    DECLARE v_count INT;
    DECLARE v_capacity INT;
    IF (NEW.offering_id != OLD.offering_id OR NEW.student_id != OLD.student_id)
       AND (EXISTS(SELECT 1 FROM attendance WHERE enrollment_id=OLD.enrollment_id)
            OR EXISTS(SELECT 1 FROM result WHERE enrollment_id=OLD.enrollment_id)) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Cannot transfer an enrollment with academic records.';
    END IF;
    IF NEW.status='Enrolled' AND (OLD.status!='Enrolled' OR OLD.offering_id!=NEW.offering_id) THEN
        SELECT enrolled_count,capacity INTO v_count,v_capacity FROM course_offering WHERE offering_id=NEW.offering_id FOR UPDATE;
        IF v_count >= v_capacity THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Course offering has reached capacity.';
        END IF;
        IF NOT EXISTS(SELECT 1 FROM student WHERE student_id=NEW.student_id AND status='Active') THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Student must be Active to enroll.';
        END IF;
    END IF;
END$$
DROP TRIGGER IF EXISTS trg_attendance_before_update$$
CREATE TRIGGER trg_attendance_before_update BEFORE UPDATE ON attendance FOR EACH ROW
BEGIN
    IF NOT EXISTS(SELECT 1 FROM enrollment WHERE enrollment_id=NEW.enrollment_id AND status='Enrolled') THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Attendance requires an active enrollment.';
    END IF;
END$$
DROP TRIGGER IF EXISTS trg_student_after_insert$$
CREATE TRIGGER trg_student_after_insert AFTER INSERT ON student FOR EACH ROW
BEGIN
    INSERT INTO audit_log(table_name,action,record_id,new_values,changed_by)
    VALUES('student','INSERT',NEW.student_id,JSON_OBJECT('roll_no',NEW.roll_no,'name',CONCAT(NEW.first_name,' ',NEW.last_name)),CURRENT_USER());
END$$

DROP TRIGGER IF EXISTS trg_student_ledger_update$$
CREATE TRIGGER trg_student_ledger_update BEFORE UPDATE ON student FOR EACH ROW
BEGIN
    IF NEW.dept_id != OLD.dept_id AND EXISTS(SELECT 1 FROM fee_payment WHERE student_id=OLD.student_id) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='A student with recorded payments cannot change department.';
    END IF;
    IF NEW.current_semester < COALESCE((SELECT MAX(semester_no) FROM fee_payment WHERE student_id=OLD.student_id), 0) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Current semester cannot be earlier than recorded payments.';
    END IF;
END$$

DELIMITER ;
