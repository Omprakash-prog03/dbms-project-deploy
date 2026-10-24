-- ============================================================================
-- SIMS SHOWCASE QUERIES - GROUP E: SET OPERATIONS (Q22 - Q23)
-- Database Engine: MySQL 8.0+
-- ============================================================================

-- Q22. UNION vs UNION ALL: Unified Campus Personnel Directory
-- Combines disparate entities with compatible projection; compares sort overhead vs pure append.
SELECT
    'Student' AS identity_type,
    s.roll_no AS unique_code,
    CONCAT(s.first_name, ' ', s.last_name) AS full_name,
    s.email,
    d.dept_code
FROM student s
JOIN department d ON s.dept_id = d.dept_id
UNION ALL
SELECT
    'Faculty' AS identity_type,
    CAST(f.faculty_id AS CHAR) AS unique_code,
    CONCAT(f.first_name, ' ', f.last_name) AS full_name,
    f.email,
    d.dept_code
FROM faculty f
JOIN department d ON f.dept_id = d.dept_id
ORDER BY identity_type, full_name;

-- Q23. Set Difference (EXCEPT): Curriculum Offerings Offered in 2024-2025 but Dropped in 2025-2026
-- Demonstrates native MySQL 8.0.31+ EXCEPT set difference operator.
SELECT c.course_code, c.title AS course_title
FROM course c
JOIN course_offering co ON c.course_id = co.course_id
WHERE co.academic_year = '2024-2025'
EXCEPT
SELECT c.course_code, c.title AS course_title
FROM course c
JOIN course_offering co ON c.course_id = co.course_id
WHERE co.academic_year = '2025-2026';
