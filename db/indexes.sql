-- ============================================================================
-- STUDENT INFORMATION MANAGEMENT SYSTEM (SIMS) - SECONDARY PERFORMANCE INDEXES
-- Purpose: B-Tree index specifications with explicit query acceleration justifications
-- ============================================================================

USE sims_db;

-- 1. Accelerates student roster lookups filtered by course offering
-- Query: SELECT s.* FROM enrollment e JOIN student s USING(student_id) WHERE e.offering_id = ?
CREATE INDEX idx_enrollment_offering_student ON enrollment(offering_id, student_id);

-- 2. Accelerates departmental cohort filtering and status aggregations
-- Query: SELECT COUNT(*) FROM student WHERE dept_id = ? AND status = 'Active'
CREATE INDEX idx_student_dept_status ON student(dept_id, status);

-- 3. Accelerates semester-wise fee ledger reconciliations
-- Query: SELECT SUM(amount) FROM fee_payment WHERE student_id = ? AND semester_no = ?
CREATE INDEX idx_payment_student_sem ON fee_payment(student_id, semester_no);

-- 4. Accelerates daily institutional attendance roll-call audits
-- Query: SELECT * FROM attendance WHERE class_date = ? AND status = 'Absent'
CREATE INDEX idx_attendance_date_status ON attendance(class_date, status);

-- 5. Accelerates gradebook lookups for an exam sorted by marks
-- Query: SELECT * FROM result WHERE exam_id = ? ORDER BY marks_obtained DESC
CREATE INDEX idx_result_exam_marks ON result(exam_id, marks_obtained);

-- 6. Accelerates pending application queue filtering on the dashboard
-- Query: SELECT * FROM admission_application WHERE status = 'Pending' ORDER BY applied_on ASC
CREATE INDEX idx_application_status_date ON admission_application(status, applied_on);
