-- ============================================================================
-- SIMS SHOWCASE QUERIES - GROUP C: SUBQUERIES (Q12 - Q16)
-- Database Engine: MySQL 8.0+
-- ============================================================================

-- Q12. Scalar Subquery in SELECT: Individual Score vs Exam Global Average
-- Evaluates an inline aggregate benchmark without joining a second aggregate table.
SELECT
    s.roll_no,
    CONCAT(s.first_name, ' ', s.last_name) AS student_name,
    c.course_code,
    r.marks_obtained,
    (
        SELECT ROUND(AVG(r2.marks_obtained), 2)
        FROM result r2
        WHERE r2.exam_id = r.exam_id
    ) AS exam_global_average,
    ROUND(r.marks_obtained - (
        SELECT AVG(r2.marks_obtained)
        FROM result r2
        WHERE r2.exam_id = r.exam_id
    ), 2) AS deviation_from_average
FROM result r
JOIN enrollment e ON r.enrollment_id = e.enrollment_id
JOIN student s ON e.student_id = s.student_id
JOIN exam ex ON r.exam_id = ex.exam_id
JOIN course_offering co ON ex.offering_id = co.offering_id
JOIN course c ON co.course_id = c.course_id
WHERE ex.exam_type = 'Final'
LIMIT 25;

-- Q13. IN / EXISTS Predicate: Active Students with Outstanding Arrears
-- Proves optimizer semi-join preference for EXISTS over IN.
SELECT
    s.student_id,
    s.roll_no,
    CONCAT(s.first_name, ' ', s.last_name) AS student_name,
    d.dept_code,
    s.current_semester
FROM student s
JOIN department d ON s.dept_id = d.dept_id
WHERE s.status = 'Active'
  AND EXISTS (
      SELECT 1
      FROM fee_structure fs
      WHERE fs.dept_id = s.dept_id
        AND fs.semester_no = s.current_semester
        AND fs.amount > (
            SELECT COALESCE(SUM(fp.amount), 0)
            FROM fee_payment fp
            WHERE fp.student_id = s.student_id
              AND fp.semester_no = s.current_semester
        )
  )
ORDER BY s.roll_no ASC;

-- Q14. Correlated Subquery: Students with CGPA Exceeding Departmental Benchmark
-- Outer query value (s.dept_id) referenced inside the inner subquery.
SELECT
    s.roll_no,
    CONCAT(s.first_name, ' ', s.last_name) AS student_name,
    d.dept_code,
    fn_student_cgpa(s.student_id) AS student_cgpa,
    (
        SELECT ROUND(AVG(fn_student_cgpa(s2.student_id)), 2)
        FROM student s2
        WHERE s2.dept_id = s.dept_id AND s2.status = 'Active'
    ) AS dept_average_cgpa
FROM student s
JOIN department d ON s.dept_id = d.dept_id
WHERE s.status = 'Active'
  AND fn_student_cgpa(s.student_id) > (
      SELECT AVG(fn_student_cgpa(s2.student_id))
      FROM student s2
      WHERE s2.dept_id = s.dept_id AND s2.status = 'Active'
  )
ORDER BY d.dept_code, student_cgpa DESC;

-- Q15. Derived Table in FROM: Departmental Aggregation Over Student Averages
-- Subquery materialization and aliasing in FROM clause.
SELECT
    dept_stats.dept_code,
    dept_stats.dept_name,
    COUNT(dept_stats.student_id) AS evaluated_students_count,
    ROUND(AVG(dept_stats.student_mean), 2) AS dept_overall_mean,
    ROUND(MAX(dept_stats.student_mean), 2) AS dept_top_mean
FROM (
    SELECT
        s.student_id,
        s.dept_id,
        d.dept_code,
        d.dept_name,
        AVG(r.marks_obtained) AS student_mean
    FROM student s
    JOIN department d ON s.dept_id = d.dept_id
    JOIN enrollment e ON s.student_id = e.student_id
    JOIN result r ON e.enrollment_id = r.enrollment_id
    GROUP BY s.student_id, s.dept_id, d.dept_code, d.dept_name
) AS dept_stats
GROUP BY dept_stats.dept_code, dept_stats.dept_name
ORDER BY dept_overall_mean DESC;

-- Q16. Quantified Comparison (ALL/ANY): High-Scoring Benchmark Students
-- Isolates student result exceeding ALL results in the same examination.
SELECT
    s.roll_no,
    CONCAT(s.first_name, ' ', s.last_name) AS student_name,
    c.course_code,
    r.marks_obtained
FROM result r
JOIN enrollment e ON r.enrollment_id = e.enrollment_id
JOIN student s ON e.student_id = s.student_id
JOIN exam ex ON r.exam_id = ex.exam_id
JOIN course_offering co ON ex.offering_id = co.offering_id
JOIN course c ON co.course_id = c.course_id
WHERE ex.exam_type = 'Final' AND co.offering_id = 1
  AND r.marks_obtained >= ALL (
      SELECT r2.marks_obtained
      FROM result r2
      WHERE r2.exam_id = ex.exam_id
  );
