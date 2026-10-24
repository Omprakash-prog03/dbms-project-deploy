-- ============================================================================
-- SIMS SHOWCASE QUERIES - GROUP F: DATA MODIFICATION DML (Q24 - Q25)
-- Database Engine: MySQL 8.0+
-- Description: Transactional modification demos with explicit ROLLBACK
-- ============================================================================

-- Q24. INSERT ... SELECT with Transaction Demo: Batch Cohort Promotion
-- Atomically snapshots changes into audit_log and updates current_semester,
-- followed by ROLLBACK to maintain pristine seed state.
START TRANSACTION;

-- Step 1: Snapshot audit ledger records via INSERT ... SELECT
INSERT INTO audit_log (table_name, action, record_id, old_values, new_values, changed_by)
SELECT
    'student',
    'UPDATE',
    s.student_id,
    JSON_OBJECT('current_semester', s.current_semester, 'status', s.status),
    JSON_OBJECT('current_semester', s.current_semester + 1, 'status', s.status),
    'batch_promotion_job'
FROM student s
WHERE s.current_semester = 1 AND s.status = 'Active';

-- Step 2: Perform batch promotion update
UPDATE student
SET current_semester = current_semester + 1
WHERE current_semester = 1 AND status = 'Active';

-- Step 3: Verify execution count
SELECT ROW_COUNT() AS total_students_promoted;

-- Step 4: Deliberate viva rollback to ensure non-destructive demonstration
ROLLBACK;


-- Q25. Multi-Table UPDATE with JOIN: Batch Academic Scholarship Fee Discount
-- Applies 10% tuition rebate on semester 2 fee for Computer Science department,
-- followed by ROLLBACK demonstration.
START TRANSACTION;

-- Apply 10% merit rebate on semester 2 fee for Computer Science department
UPDATE fee_structure fs
JOIN department d ON fs.dept_id = d.dept_id
SET fs.amount = fs.amount * 0.90
WHERE fs.semester_no = 2 AND d.dept_code = 'CSE';

-- Verify the revised fee structure
SELECT
    d.dept_code,
    fs.semester_no,
    fs.amount AS discounted_tuition_fee
FROM fee_structure fs
JOIN department d ON fs.dept_id = d.dept_id
WHERE fs.semester_no = 2 AND d.dept_code = 'CSE';

-- Rollback demonstration to maintain seed integrity
ROLLBACK;
