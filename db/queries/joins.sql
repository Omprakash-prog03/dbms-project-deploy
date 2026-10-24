-- ============================================================================
-- SIMS SHOWCASE QUERIES - GROUP A: RELATIONAL JOINS (Q01 - Q06)
-- Database Engine: MySQL 8.0+
-- ============================================================================

-- Q01. Inner Join: Course offerings with instructor and department names
-- Demonstrates standard multi-table inner joins navigating 1:N relationships.
SELECT
    co.offering_id,
    c.course_code,
    c.title AS course_title,
    c.credits,
    d.dept_code,
    d.dept_name,
    CONCAT(f.first_name, ' ', f.last_name) AS instructor_name,
    co.academic_year,
    co.term,
    co.capacity,
    co.enrolled_count
FROM course_offering co
JOIN course c ON co.course_id = c.course_id
JOIN department d ON c.dept_id = d.dept_id
JOIN faculty f ON co.faculty_id = f.faculty_id
ORDER BY c.course_code ASC, co.academic_year DESC;

-- Q02. Left Outer Join: Students with zero course enrollments
-- Demonstrates identifying unassigned records using anti-join syntax.
SELECT
    s.student_id,
    s.roll_no,
    CONCAT(s.first_name, ' ', s.last_name) AS student_name,
    s.email,
    d.dept_code,
    s.current_semester,
    s.status
FROM student s
JOIN department d ON s.dept_id = d.dept_id
LEFT JOIN enrollment e ON s.student_id = e.student_id
WHERE e.enrollment_id IS NULL
ORDER BY s.roll_no ASC;

-- Q03. Full Outer Join Equivalent: Departments without courses & courses without departments
-- Demonstrates ANSI SQL FULL OUTER JOIN emulation in MySQL via UNION of directed outer joins.
SELECT
    d.dept_code,
    d.dept_name,
    c.course_code,
    c.title AS course_title
FROM department d
LEFT JOIN course c ON d.dept_id = c.dept_id
UNION
SELECT
    d.dept_code,
    d.dept_name,
    c.course_code,
    c.title AS course_title
FROM department d
RIGHT JOIN course c ON d.dept_id = c.dept_id
WHERE d.dept_id IS NULL
ORDER BY dept_code, course_code;

-- Q04. Self-Join: Faculty members alongside their Head of Department (HoD)
-- Demonstrates traversing unary recursive relationships using aliases.
SELECT
    f.faculty_id,
    CONCAT(f.first_name, ' ', f.last_name) AS faculty_name,
    f.designation,
    d.dept_code,
    CONCAT(hod.first_name, ' ', hod.last_name) AS hod_name,
    CASE
        WHEN f.faculty_id = d.hod_faculty_id THEN 'Yes (Self)'
        ELSE 'No'
    END AS is_department_head
FROM faculty f
JOIN department d ON f.dept_id = d.dept_id
LEFT JOIN faculty hod ON d.hod_faculty_id = hod.faculty_id
ORDER BY d.dept_code, f.designation DESC;

-- Q05. Deep Multi-Table Join: 5-Table Academic Transcript Traversal
-- Traverses: student -> enrollment -> course_offering -> course -> result -> exam.
SELECT
    s.roll_no,
    CONCAT(s.first_name, ' ', s.last_name) AS student_name,
    c.course_code,
    c.title AS course_title,
    co.academic_year,
    co.term,
    ex.exam_type,
    ex.max_marks,
    r.marks_obtained,
    ROUND((r.marks_obtained / ex.max_marks) * 100, 1) AS percentage,
    fn_grade(ROUND((r.marks_obtained / ex.max_marks) * 100, 1)) AS letter_grade
FROM student s
JOIN enrollment e ON s.student_id = e.student_id
JOIN course_offering co ON e.offering_id = co.offering_id
JOIN course c ON co.course_id = c.course_id
JOIN exam ex ON co.offering_id = ex.offering_id
JOIN result r ON ex.exam_id = r.exam_id AND e.enrollment_id = r.enrollment_id
ORDER BY s.roll_no, c.course_code, ex.exam_type;

-- Q06. Cross Join: Combinatorial Examination Slot Matrix
-- Generates Cartesian product of active courses with exam scheduling slots.
SELECT
    c.course_code,
    c.title AS course_title,
    slot.day_name,
    slot.time_window,
    slot.hall_number
FROM course c
CROSS JOIN (
    SELECT 'Monday' AS day_name, '09:00 - 12:00' AS time_window, 'LH-101' AS hall_number
    UNION ALL SELECT 'Tuesday', '09:00 - 12:00', 'LH-102'
    UNION ALL SELECT 'Wednesday', '14:00 - 17:00', 'LH-101'
    UNION ALL SELECT 'Thursday', '14:00 - 17:00', 'LH-103'
    UNION ALL SELECT 'Friday', '09:00 - 12:00', 'LH-102'
) slot
WHERE c.semester_no = 1
ORDER BY c.course_code, slot.day_name;
