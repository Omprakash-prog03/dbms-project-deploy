-- ============================================================================
-- STUDENT INFORMATION MANAGEMENT SYSTEM (SIMS) - SYSTEM REPORTING VIEWS
-- Engine: MySQL 8.0+
-- Description: Aggregated relational views providing real-time metrics for UI.
-- ============================================================================

USE sims_db;

-- 1. Comprehensive Student Profile Overview
CREATE OR REPLACE VIEW v_student_overview AS
SELECT
    s.student_id,
    s.roll_no,
    CONCAT(s.first_name, ' ', s.last_name) AS full_name,
    s.email,
    s.phone,
    s.gender,
    s.current_semester,
    s.status,
    s.admission_date,
    d.dept_id,
    d.dept_code,
    d.dept_name,
    COUNT(DISTINCT e.offering_id) AS total_courses_enrolled,
    ROUND(COALESCE(AVG(r.marks_obtained), 0), 2) AS average_marks
FROM student s
JOIN department d ON s.dept_id = d.dept_id
LEFT JOIN enrollment e ON s.student_id = e.student_id AND e.status = 'Enrolled'
LEFT JOIN result r ON e.enrollment_id = r.enrollment_id
GROUP BY s.student_id, d.dept_id, s.admission_date;

-- 2. Course Offering Statistics & Capacity Utilization
CREATE OR REPLACE VIEW v_course_offering_stats AS
SELECT
    co.offering_id,
    c.course_id,
    c.course_code,
    c.title AS course_title,
    c.credits,
    d.dept_id,
    d.dept_code,
    d.dept_name,
    co.faculty_id,
    CONCAT(f.first_name, ' ', f.last_name) AS instructor_name,
    co.academic_year,
    co.term,
    co.capacity,
    co.enrolled_count,
    ROUND((co.enrolled_count / co.capacity) * 100, 1) AS utilization_pct,
    CASE
        WHEN co.enrolled_count >= co.capacity THEN 'FULL'
        WHEN co.enrolled_count >= (co.capacity * 0.8) THEN 'ALMOST FULL'
        ELSE 'AVAILABLE'
    END AS seat_status
FROM course_offering co
JOIN course c ON co.course_id = c.course_id
JOIN department d ON c.dept_id = d.dept_id
JOIN faculty f ON co.faculty_id = f.faculty_id;

-- 3. Fee Status, Arrears & Defaulter Flagging
CREATE OR REPLACE VIEW v_fee_status AS
SELECT
    s.student_id,
    s.roll_no,
    CONCAT(s.first_name, ' ', s.last_name) AS full_name,
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

-- 4. Attendance Percentage Summary
CREATE OR REPLACE VIEW v_attendance_summary AS
SELECT
    e.enrollment_id,
    s.student_id,
    s.roll_no,
    CONCAT(s.first_name, ' ', s.last_name) AS student_name,
    c.course_code,
    c.title AS course_title,
    co.academic_year,
    co.term,
    COUNT(a.attendance_id) AS total_classes,
    SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) AS present_count,
    SUM(CASE WHEN a.status = 'Late' THEN 1 ELSE 0 END) AS late_count,
    SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) AS absent_count,
    ROUND(
        (SUM(CASE WHEN a.status IN ('Present', 'Late') THEN 1 ELSE 0 END) /
        NULLIF(COUNT(a.attendance_id), 0)) * 100, 1
    ) AS attendance_percentage
FROM enrollment e
JOIN student s ON e.student_id = s.student_id
JOIN course_offering co ON e.offering_id = co.offering_id
JOIN course c ON co.course_id = c.course_id
LEFT JOIN attendance a ON e.enrollment_id = a.enrollment_id
GROUP BY e.enrollment_id;

-- 5. Pending Admissions Queue
CREATE OR REPLACE VIEW v_pending_approvals AS
SELECT
    aa.application_id,
    aa.applicant_name,
    aa.email,
    aa.phone,
    d.dept_id,
    d.dept_code,
    d.dept_name,
    aa.applied_on,
    aa.status
FROM admission_application aa
JOIN department d ON aa.dept_id = d.dept_id
WHERE aa.status = 'Pending'
ORDER BY aa.applied_on ASC;

-- 6. Monthly Admissions vs Enrollments (Feeds the Jobgio Statistics Bar Chart)
CREATE OR REPLACE VIEW v_monthly_admissions_enrollments AS
WITH RECURSIVE months AS (
    SELECT 1 AS month_num
    UNION ALL
    SELECT month_num + 1 FROM months WHERE month_num < 12
)
SELECT
    m.month_num,
    DATE_FORMAT(STR_TO_DATE(CONCAT('2026-', m.month_num, '-01'), '%Y-%m-%d'), '%b') AS month_name,
    COALESCE(adm.admissions_count, 0) AS admissions_count,
    COALESCE(enr.enrollments_count, 0) AS enrollments_count
FROM months m
LEFT JOIN (
    SELECT MONTH(admission_date) AS m_num, COUNT(*) AS admissions_count
    FROM student
    WHERE YEAR(admission_date) = 2026
    GROUP BY MONTH(admission_date)
) adm ON m.month_num = adm.m_num
LEFT JOIN (
    SELECT MONTH(enroll_date) AS m_num, COUNT(*) AS enrollments_count
    FROM enrollment
    WHERE YEAR(enroll_date) = 2026
    GROUP BY MONTH(enroll_date)
) enr ON m.month_num = enr.m_num
ORDER BY m.month_num;
