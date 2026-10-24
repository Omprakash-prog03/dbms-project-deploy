-- ============================================================================
-- SIMS SHOWCASE QUERIES - GROUP B: AGGREGATIONS & GROUPING (Q07 - Q11)
-- Database Engine: MySQL 8.0+
-- ============================================================================

-- Q07. GROUP BY + HAVING: Departmental Cohorts Exceeding Size Threshold
-- Distinguishes WHERE (row filter) from HAVING (aggregate group filter).
SELECT
    d.dept_code,
    d.dept_name,
    COUNT(s.student_id) AS total_enrolled_students,
    SUM(CASE WHEN s.status = 'Active' THEN 1 ELSE 0 END) AS active_students,
    ROUND(AVG(s.current_semester), 1) AS avg_current_semester
FROM department d
JOIN student s ON d.dept_id = s.dept_id
GROUP BY d.dept_id, d.dept_code, d.dept_name
HAVING COUNT(s.student_id) > 25
ORDER BY total_enrolled_students DESC;

-- Q08. Statistical Distribution: Comprehensive Marks Summary Per Course Offering
-- Calculates COUNT, SUM, AVG, MIN, MAX, STDDEV per exam.
SELECT
    co.offering_id,
    c.course_code,
    c.title AS course_title,
    ex.exam_type,
    ex.max_marks,
    COUNT(r.result_id) AS evaluations_conducted,
    ROUND(AVG(r.marks_obtained), 2) AS average_score,
    MIN(r.marks_obtained) AS lowest_score,
    MAX(r.marks_obtained) AS highest_score,
    ROUND(STDDEV(r.marks_obtained), 2) AS standard_deviation
FROM course_offering co
JOIN course c ON co.course_id = c.course_id
JOIN exam ex ON co.offering_id = ex.offering_id
JOIN result r ON ex.exam_id = r.exam_id
GROUP BY co.offering_id, c.course_code, c.title, ex.exam_type, ex.max_marks
ORDER BY c.course_code, ex.exam_type;

-- Q09. Multi-Tier Financial Aggregation: Tuition Collected by Department & Semester
-- Hierarchical grouping for university financial reconciliations.
SELECT
    d.dept_code,
    d.dept_name,
    fp.semester_no,
    COUNT(DISTINCT fp.payment_id) AS transaction_count,
    COUNT(DISTINCT fp.student_id) AS students_paid_count,
    SUM(fp.amount) AS total_tuition_collected
FROM department d
JOIN student s ON d.dept_id = s.dept_id
JOIN fee_payment fp ON s.student_id = fp.student_id
GROUP BY d.dept_id, d.dept_code, d.dept_name, fp.semester_no
ORDER BY d.dept_code, fp.semester_no ASC;

-- Q10. Conditional Aggregation: Course Pass Rates (Passing Threshold >= 40%)
-- Pivots pass/fail outcomes into ratios using conditional SUM.
SELECT
    co.offering_id,
    c.course_code,
    c.title AS course_title,
    ex.exam_type,
    COUNT(r.result_id) AS total_candidates,
    SUM(CASE WHEN (r.marks_obtained / ex.max_marks) >= 0.40 THEN 1 ELSE 0 END) AS passed_candidates,
    SUM(CASE WHEN (r.marks_obtained / ex.max_marks) < 0.40 THEN 1 ELSE 0 END) AS failed_candidates,
    ROUND((SUM(CASE WHEN (r.marks_obtained / ex.max_marks) >= 0.40 THEN 1 ELSE 0 END) / COUNT(r.result_id)) * 100, 2) AS pass_percentage
FROM course_offering co
JOIN course c ON co.course_id = c.course_id
JOIN exam ex ON co.offering_id = ex.offering_id
JOIN result r ON ex.exam_id = r.exam_id
GROUP BY co.offering_id, c.course_code, c.title, ex.exam_type;

-- Q11. Institutional Attendance Distribution: University Attendance Quality Ratio
-- Aggregates present, late, absent roll-calls across departments.
SELECT
    d.dept_code,
    COUNT(a.attendance_id) AS total_recorded_sessions,
    SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) AS present_count,
    SUM(CASE WHEN a.status = 'Late' THEN 1 ELSE 0 END) AS late_count,
    SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) AS absent_count,
    ROUND((SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) / COUNT(a.attendance_id)) * 100, 1) AS attendance_rate
FROM department d
JOIN student s ON d.dept_id = s.dept_id
JOIN enrollment e ON s.student_id = e.student_id
JOIN attendance a ON e.enrollment_id = a.enrollment_id
GROUP BY d.dept_id, d.dept_code
ORDER BY attendance_rate DESC;
