-- ============================================================================
-- SIMS SHOWCASE QUERIES - GROUP D: WINDOW FUNCTIONS & CTES (Q17 - Q21)
-- Database Engine: MySQL 8.0+
-- ============================================================================

-- Q17. DENSE_RANK Partitioning: Top 3 Scholars Per Academic Department
-- Analytic ranking partitioned by department; no gaps in ranking sequences.
WITH departmental_rankings AS (
    SELECT
        s.student_id,
        s.roll_no,
        CONCAT(s.first_name, ' ', s.last_name) AS student_name,
        d.dept_code,
        fn_student_cgpa(s.student_id) AS cgpa,
        DENSE_RANK() OVER (
            PARTITION BY s.dept_id
            ORDER BY fn_student_cgpa(s.student_id) DESC
        ) AS rank_within_dept
    FROM student s
    JOIN department d ON s.dept_id = d.dept_id
    WHERE s.status = 'Active'
)
SELECT
    dept_code,
    rank_within_dept,
    roll_no,
    student_name,
    cgpa
FROM departmental_rankings
WHERE rank_within_dept <= 3
ORDER BY dept_code, rank_within_dept ASC;

-- Q18. Cumulative Window Aggregation: Running Total of University Tuition Receipts
-- Demonstrates unbounded preceding window framing.
SELECT
    calendar_month,
    monthly_collection,
    SUM(monthly_collection) OVER (
        ORDER BY calendar_month
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS cumulative_revenue_to_date
FROM (
    SELECT
        DATE_FORMAT(paid_on, '%Y-%m') AS calendar_month,
        SUM(amount) AS monthly_collection
    FROM fee_payment
    GROUP BY DATE_FORMAT(paid_on, '%Y-%m')
) monthly_breakdown
ORDER BY calendar_month ASC;

-- Q19. Analytic Offset LAG: Semester-Over-Semester Student Performance Delta
-- Calculates performance change between successive terms without self-joins.
WITH sem_scores AS (
    SELECT
        s.student_id,
        s.roll_no,
        CONCAT(s.first_name, ' ', s.last_name) AS student_name,
        c.semester_no,
        ROUND(AVG(r.marks_obtained), 2) AS semester_average
    FROM student s
    JOIN enrollment e ON s.student_id = e.student_id
    JOIN course_offering co ON e.offering_id = co.offering_id
    JOIN course c ON co.course_id = c.course_id
    JOIN result r ON e.enrollment_id = r.enrollment_id
    GROUP BY s.student_id, s.roll_no, student_name, c.semester_no
)
SELECT
    student_id,
    roll_no,
    student_name,
    semester_no,
    semester_average,
    LAG(semester_average, 1) OVER (
        PARTITION BY student_id
        ORDER BY semester_no
    ) AS prior_sem_average,
    ROUND(
        semester_average - LAG(semester_average, 1) OVER (
            PARTITION BY student_id
            ORDER BY semester_no
        ), 2
    ) AS performance_delta
FROM sem_scores
ORDER BY student_id, semester_no ASC;

-- Q20. Recursive CTE: Generating 8-Semester Curriculum Progression Matrix
-- Demonstrates anchor and recursive member logic without physical tables.
WITH RECURSIVE semester_progression AS (
    -- Anchor Member
    SELECT 1 AS sem_idx, 'Semester 1 (Autumn)' AS semester_title
    UNION ALL
    -- Recursive Member
    SELECT sem_idx + 1,
           CONCAT('Semester ', sem_idx + 1, ' (', CASE WHEN (sem_idx + 1) % 2 = 1 THEN 'Autumn' ELSE 'Spring' END, ')')
    FROM semester_progression
    WHERE sem_idx < 8
)
SELECT
    sp.sem_idx AS semester_number,
    sp.semester_title,
    COUNT(c.course_id) AS total_courses_designed,
    COALESCE(SUM(c.credits), 0) AS total_credits_prescribed
FROM semester_progression sp
LEFT JOIN course c ON sp.sem_idx = c.semester_no
GROUP BY sp.sem_idx, sp.semester_title
ORDER BY sp.sem_idx ASC;

-- Q21. Multi-Stage CTE: Fee Defaulter Audit with Dynamic Late Fines
-- Modular CTE pipeline computing arrears and applying tier-based late penalties.
WITH current_dues AS (
    SELECT
        s.student_id,
        s.roll_no,
        CONCAT(s.first_name, ' ', s.last_name) AS student_name,
        d.dept_code,
        s.current_semester,
        fs.amount AS tuition_due,
        COALESCE((
            SELECT SUM(fp.amount)
            FROM fee_payment fp
            WHERE fp.student_id = s.student_id AND fp.semester_no = s.current_semester
        ), 0) AS total_paid
    FROM student s
    JOIN department d ON s.dept_id = d.dept_id
    JOIN fee_structure fs ON d.dept_id = fs.dept_id AND s.current_semester = fs.semester_no
    WHERE s.status = 'Active'
),
balance_computed AS (
    SELECT
        student_id, roll_no, student_name, dept_code, current_semester,
        tuition_due, total_paid,
        (tuition_due - total_paid) AS balance_remaining,
        CASE
            WHEN (tuition_due - total_paid) > 20000 THEN 2500.00
            WHEN (tuition_due - total_paid) > 0 THEN 1000.00
            ELSE 0.00
        END AS penalty_fine
    FROM current_dues
    WHERE (tuition_due - total_paid) > 0
)
SELECT
    student_id,
    roll_no,
    student_name,
    dept_code,
    current_semester,
    tuition_due,
    total_paid,
    balance_remaining,
    penalty_fine,
    (balance_remaining + penalty_fine) AS total_outstanding
FROM balance_computed
ORDER BY balance_remaining DESC;
