-- SQLite cumulative migrations 1–2: consistency guards and audit parity with the MySQL schema.
DROP TRIGGER IF EXISTS trg_enr_upd;
DROP TRIGGER IF EXISTS trg_enr_cap;
DROP TRIGGER IF EXISTS trg_enr_active;

CREATE TRIGGER trg_enr_upd AFTER UPDATE OF status, offering_id ON enrollment
BEGIN
 UPDATE course_offering SET enrolled_count = MAX(0, enrolled_count - 1)
 WHERE offering_id = OLD.offering_id AND OLD.status = 'Enrolled';
 UPDATE course_offering SET enrolled_count = enrolled_count + 1
 WHERE offering_id = NEW.offering_id AND NEW.status = 'Enrolled';
END;
CREATE TRIGGER trg_enr_cap BEFORE INSERT ON enrollment
WHEN NEW.status = 'Enrolled' AND (SELECT enrolled_count >= capacity FROM course_offering WHERE offering_id = NEW.offering_id)
BEGIN SELECT RAISE(ABORT, 'Course offering has reached capacity.'); END;
CREATE TRIGGER trg_enr_active BEFORE INSERT ON enrollment
WHEN NEW.status = 'Enrolled' AND (SELECT status FROM student WHERE student_id = NEW.student_id) != 'Active'
BEGIN SELECT RAISE(ABORT, 'Student must be Active to enroll.'); END;
CREATE TRIGGER IF NOT EXISTS trg_enr_update_guard BEFORE UPDATE OF status, offering_id ON enrollment
WHEN NEW.status = 'Enrolled' AND (OLD.status != 'Enrolled' OR OLD.offering_id != NEW.offering_id)
BEGIN
 SELECT CASE WHEN (SELECT enrolled_count >= capacity FROM course_offering WHERE offering_id = NEW.offering_id)
 THEN RAISE(ABORT, 'Course offering has reached capacity.') END;
 SELECT CASE WHEN (SELECT status FROM student WHERE student_id = NEW.student_id) != 'Active'
 THEN RAISE(ABORT, 'Student must be Active to enroll.') END;
END;
CREATE TRIGGER IF NOT EXISTS trg_enr_transfer_guard BEFORE UPDATE OF offering_id, student_id ON enrollment
WHEN (NEW.offering_id != OLD.offering_id OR NEW.student_id != OLD.student_id)
 AND (EXISTS(SELECT 1 FROM attendance WHERE enrollment_id = OLD.enrollment_id) OR EXISTS(SELECT 1 FROM result WHERE enrollment_id = OLD.enrollment_id))
BEGIN SELECT RAISE(ABORT, 'Cannot transfer an enrollment with academic records.'); END;

CREATE TRIGGER IF NOT EXISTS trg_attendance_guard_insert BEFORE INSERT ON attendance
WHEN NOT EXISTS(SELECT 1 FROM enrollment WHERE enrollment_id=NEW.enrollment_id AND status='Enrolled')
BEGIN SELECT RAISE(ABORT, 'Attendance requires an active enrollment.'); END;
CREATE TRIGGER IF NOT EXISTS trg_attendance_guard_update BEFORE UPDATE ON attendance
WHEN NOT EXISTS(SELECT 1 FROM enrollment WHERE enrollment_id=NEW.enrollment_id AND status='Enrolled')
BEGIN SELECT RAISE(ABORT, 'Attendance requires an active enrollment.'); END;
CREATE TRIGGER IF NOT EXISTS trg_result_offering_insert BEFORE INSERT ON result
WHEN NOT EXISTS(SELECT 1 FROM enrollment e JOIN exam ex ON ex.offering_id=e.offering_id WHERE e.enrollment_id=NEW.enrollment_id AND ex.exam_id=NEW.exam_id AND e.status='Enrolled')
BEGIN SELECT RAISE(ABORT, 'Result must match an active enrollment in this exam offering.'); END;
CREATE TRIGGER IF NOT EXISTS trg_result_offering_update BEFORE UPDATE ON result
WHEN NOT EXISTS(SELECT 1 FROM enrollment e JOIN exam ex ON ex.offering_id=e.offering_id WHERE e.enrollment_id=NEW.enrollment_id AND ex.exam_id=NEW.exam_id AND e.status='Enrolled')
BEGIN SELECT RAISE(ABORT, 'Result must match an active enrollment in this exam offering.'); END;

CREATE TRIGGER IF NOT EXISTS trg_student_age_insert BEFORE INSERT ON student
WHEN date(NEW.dob) IS NULL OR date(NEW.admission_date) IS NULL OR date(NEW.dob,'+15 years') > date(NEW.admission_date)
BEGIN SELECT RAISE(ABORT, 'Student must be at least 15 on the admission date.'); END;
CREATE TRIGGER IF NOT EXISTS trg_student_age_update BEFORE UPDATE OF dob, admission_date ON student
WHEN date(NEW.dob) IS NULL OR date(NEW.admission_date) IS NULL OR date(NEW.dob,'+15 years') > date(NEW.admission_date)
BEGIN SELECT RAISE(ABORT, 'Student must be at least 15 on the admission date.'); END;

CREATE TRIGGER IF NOT EXISTS trg_student_audit_ins AFTER INSERT ON student
BEGIN INSERT INTO audit_log(table_name,action,record_id,new_values,changed_by)
 VALUES('student','INSERT',NEW.student_id,JSON_OBJECT('roll_no',NEW.roll_no,'name',NEW.first_name || ' ' || NEW.last_name),'database'); END;
CREATE TRIGGER IF NOT EXISTS trg_student_audit_upd AFTER UPDATE ON student
BEGIN INSERT INTO audit_log(table_name,action,record_id,old_values,new_values,changed_by)
 VALUES('student','UPDATE',NEW.student_id,JSON_OBJECT('status',OLD.status,'semester',OLD.current_semester),JSON_OBJECT('status',NEW.status,'semester',NEW.current_semester),'database'); END;
CREATE TRIGGER IF NOT EXISTS trg_student_audit_del AFTER DELETE ON student
BEGIN INSERT INTO audit_log(table_name,action,record_id,old_values,changed_by)
 VALUES('student','DELETE',OLD.student_id,JSON_OBJECT('roll_no',OLD.roll_no,'name',OLD.first_name || ' ' || OLD.last_name),'database'); END;

CREATE TRIGGER IF NOT EXISTS trg_user_role_insert BEFORE INSERT ON app_user
WHEN NOT ((NEW.role='admin' AND NEW.student_id IS NULL AND NEW.faculty_id IS NULL)
 OR (NEW.role='student' AND NEW.student_id IS NOT NULL AND NEW.faculty_id IS NULL)
 OR (NEW.role='faculty' AND NEW.student_id IS NULL AND NEW.faculty_id IS NOT NULL))
BEGIN SELECT RAISE(ABORT, 'Account role does not match its linked profile.'); END;
CREATE TRIGGER IF NOT EXISTS trg_user_role_update BEFORE UPDATE ON app_user
WHEN NOT ((NEW.role='admin' AND NEW.student_id IS NULL AND NEW.faculty_id IS NULL)
 OR (NEW.role='student' AND NEW.student_id IS NOT NULL AND NEW.faculty_id IS NULL)
 OR (NEW.role='faculty' AND NEW.student_id IS NULL AND NEW.faculty_id IS NOT NULL))
BEGIN SELECT RAISE(ABORT, 'Account role does not match its linked profile.'); END;
-- Updating a profile cannot relabel or hide existing financial history.
CREATE TRIGGER IF NOT EXISTS trg_student_ledger_update BEFORE UPDATE OF dept_id, current_semester ON student
BEGIN
 SELECT CASE WHEN NEW.dept_id != OLD.dept_id AND EXISTS(SELECT 1 FROM fee_payment WHERE student_id=OLD.student_id)
 THEN RAISE(ABORT, 'A student with recorded payments cannot change department.') END;
 SELECT CASE WHEN NEW.current_semester < COALESCE((SELECT MAX(semester_no) FROM fee_payment WHERE student_id=OLD.student_id), 0)
 THEN RAISE(ABORT, 'Current semester cannot be earlier than recorded payments.') END;
END;

-- Currency is compared at cent precision, never at binary floating-point epsilon.
DROP VIEW IF EXISTS v_fee_status;
CREATE VIEW v_fee_status AS
SELECT
    s.student_id,
    s.roll_no,
    s.first_name || ' ' || s.last_name AS full_name,
    d.dept_id,
    d.dept_code,
    s.current_semester,
    fs.amount AS semester_fee_due,
    ROUND(COALESCE(SUM(fp.amount), 0), 2) AS total_paid,
    ROUND(fs.amount - ROUND(COALESCE(SUM(fp.amount), 0), 2), 2) AS balance_due,
    CASE
        WHEN ROUND(COALESCE(SUM(fp.amount), 0), 2) >= fs.amount THEN 'Fully Paid'
        WHEN ROUND(COALESCE(SUM(fp.amount), 0), 2) > 0 THEN 'Partial'
        ELSE 'Unpaid'
    END AS payment_status,
    CASE
        WHEN ROUND(fs.amount - ROUND(COALESCE(SUM(fp.amount), 0), 2), 2) > 0 THEN 1
        ELSE 0
    END AS is_defaulter
FROM student s
JOIN department d ON s.dept_id = d.dept_id
JOIN fee_structure fs ON d.dept_id = fs.dept_id AND s.current_semester = fs.semester_no
LEFT JOIN fee_payment fp ON s.student_id = fp.student_id AND s.current_semester = fp.semester_no
WHERE s.status = 'Active'
GROUP BY s.student_id, fs.amount;
PRAGMA user_version = 2;
