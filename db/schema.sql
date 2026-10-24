-- ============================================================================
-- STUDENT INFORMATION MANAGEMENT SYSTEM (SIMS) - CORE RELATIONAL SCHEMA
-- Database Engine: MySQL 8.0+ | Storage Engine: InnoDB | Charset: utf8mb4
-- Description: Fully normalized (3NF/BCNF) relational schema with PK, FK,
--              UNIQUE, and CHECK constraints for academic and financial operations.
-- ============================================================================

DROP DATABASE IF EXISTS sims_db;
CREATE DATABASE sims_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE sims_db;

-- 1. DEPARTMENT
-- Master table for degree-granting academic departments.
-- hod_faculty_id is deferred with ALTER TABLE to avoid circular FK definition.
CREATE TABLE department (
    dept_id INT AUTO_INCREMENT PRIMARY KEY,
    dept_code VARCHAR(10) NOT NULL,
    dept_name VARCHAR(100) NOT NULL,
    hod_faculty_id INT NULL,
    established_year INT NOT NULL,
    CONSTRAINT uk_dept_code UNIQUE (dept_code),
    CONSTRAINT uk_dept_name UNIQUE (dept_name),
    CONSTRAINT chk_dept_year CHECK (established_year >= 1900)
) ENGINE=InnoDB;

-- 2. FACULTY
-- Instructional and research staff members.
-- ON DELETE RESTRICT on dept_id prevents orphan academic employees.
CREATE TABLE faculty (
    faculty_id INT AUTO_INCREMENT PRIMARY KEY,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    email VARCHAR(100) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    dept_id INT NOT NULL,
    designation ENUM('Professor', 'Associate Professor', 'Assistant Professor', 'Lecturer') NOT NULL,
    hire_date DATE NOT NULL,
    salary DECIMAL(10,2) NOT NULL,
    status ENUM('Active', 'On Leave', 'Resigned', 'Retired') NOT NULL DEFAULT 'Active',
    CONSTRAINT uk_faculty_email UNIQUE (email),
    CONSTRAINT chk_faculty_salary CHECK (salary > 0),
    CONSTRAINT fk_faculty_dept FOREIGN KEY (dept_id)
        REFERENCES department(dept_id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

-- Deferred HoD Foreign Key on department
-- ON DELETE SET NULL allows department to remain active if HoD resigns/retires.
ALTER TABLE department
    ADD CONSTRAINT fk_dept_hod FOREIGN KEY (hod_faculty_id)
        REFERENCES faculty(faculty_id) ON DELETE SET NULL ON UPDATE CASCADE;

-- 3. STUDENT
-- Matriculated undergraduate/graduate student master record.
-- Age constraint enforces minimum matriculation age of 15 years.
CREATE TABLE student (
    student_id INT AUTO_INCREMENT PRIMARY KEY,
    roll_no VARCHAR(20) NOT NULL,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    email VARCHAR(100) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    dob DATE NOT NULL,
    gender ENUM('Male', 'Female', 'Other') NOT NULL,
    address TEXT NOT NULL,
    dept_id INT NOT NULL,
    admission_date DATE NOT NULL,
    current_semester TINYINT NOT NULL DEFAULT 1,
    status ENUM('Active', 'Graduated', 'Suspended', 'Dropped') NOT NULL DEFAULT 'Active',
    photo_url VARCHAR(255) NULL,
    CONSTRAINT uk_student_roll UNIQUE (roll_no),
    CONSTRAINT uk_student_email UNIQUE (email),
    CONSTRAINT chk_student_age CHECK (dob <= admission_date - INTERVAL 15 YEAR),
    CONSTRAINT chk_student_semester CHECK (current_semester BETWEEN 1 AND 8),
    CONSTRAINT fk_student_dept FOREIGN KEY (dept_id)
        REFERENCES department(dept_id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

-- 4. GUARDIAN (Weak Entity)
-- Existence-dependent emergency contact entity; kept out of student for 3NF.
-- ON DELETE CASCADE wipes guardians if student master record is expunged.
CREATE TABLE guardian (
    guardian_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    name VARCHAR(100) NOT NULL,
    relation VARCHAR(50) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    CONSTRAINT fk_guardian_student FOREIGN KEY (student_id)
        REFERENCES student(student_id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;

-- 5. COURSE
-- Approved institutional syllabus catalog entries.
-- Credits restricted to 1..6 academic credits.
CREATE TABLE course (
    course_id INT AUTO_INCREMENT PRIMARY KEY,
    course_code VARCHAR(10) NOT NULL,
    title VARCHAR(150) NOT NULL,
    credits TINYINT NOT NULL,
    dept_id INT NOT NULL,
    semester_no TINYINT NOT NULL,
    CONSTRAINT uk_course_code UNIQUE (course_code),
    CONSTRAINT chk_course_credits CHECK (credits BETWEEN 1 AND 6),
    CONSTRAINT chk_course_sem CHECK (semester_no BETWEEN 1 AND 8),
    CONSTRAINT fk_course_dept FOREIGN KEY (dept_id)
        REFERENCES department(dept_id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

-- 6. COURSE_OFFERING
-- Dynamic semester offering of a catalog course.
-- Decouples catalog syllabus from term-specific scheduling.
-- enrolled_count is a justified denormalized column maintained by triggers.
CREATE TABLE course_offering (
    offering_id INT AUTO_INCREMENT PRIMARY KEY,
    course_id INT NOT NULL,
    faculty_id INT NOT NULL,
    academic_year VARCHAR(9) NOT NULL,
    term ENUM('Fall', 'Spring', 'Summer') NOT NULL,
    capacity SMALLINT NOT NULL,
    enrolled_count SMALLINT NOT NULL DEFAULT 0,
    CONSTRAINT uk_offering UNIQUE (course_id, academic_year, term),
    CONSTRAINT chk_offering_capacity CHECK (capacity > 0),
    CONSTRAINT chk_offering_count CHECK (enrolled_count >= 0),
    CONSTRAINT fk_offering_course FOREIGN KEY (course_id)
        REFERENCES course(course_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_offering_faculty FOREIGN KEY (faculty_id)
        REFERENCES faculty(faculty_id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

-- 7. ENROLLMENT (Associative Junction Table for M:N relationship)
-- Resolves M:N between student and course_offering.
-- Composite UNIQUE prevents duplicate student registration in same offering.
CREATE TABLE enrollment (
    enrollment_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    offering_id INT NOT NULL,
    enroll_date DATE NOT NULL,
    status ENUM('Enrolled', 'Dropped', 'Completed') NOT NULL DEFAULT 'Enrolled',
    CONSTRAINT uk_enrollment UNIQUE (student_id, offering_id),
    CONSTRAINT fk_enrollment_student FOREIGN KEY (student_id)
        REFERENCES student(student_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_enrollment_offering FOREIGN KEY (offering_id)
        REFERENCES course_offering(offering_id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

-- 8. ATTENDANCE
-- Granular daily roll-call tracking for enrolled students.
-- Composite UNIQUE ensures one attendance entry per student per calendar date.
CREATE TABLE attendance (
    attendance_id INT AUTO_INCREMENT PRIMARY KEY,
    enrollment_id INT NOT NULL,
    class_date DATE NOT NULL,
    status ENUM('Present', 'Absent', 'Late') NOT NULL,
    CONSTRAINT uk_attendance UNIQUE (enrollment_id, class_date),
    CONSTRAINT fk_attendance_enrollment FOREIGN KEY (enrollment_id)
        REFERENCES enrollment(enrollment_id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;

-- 9. EXAM
-- Scheduled evaluations (Internal, Midterm, Final) for an offering.
CREATE TABLE exam (
    exam_id INT AUTO_INCREMENT PRIMARY KEY,
    offering_id INT NOT NULL,
    exam_type ENUM('Internal', 'Midterm', 'Final') NOT NULL,
    max_marks DECIMAL(5,2) NOT NULL,
    exam_date DATE NOT NULL,
    CONSTRAINT uk_exam_offering UNIQUE (offering_id, exam_type),
    CONSTRAINT chk_exam_max CHECK (max_marks > 0),
    CONSTRAINT fk_exam_offering FOREIGN KEY (offering_id)
        REFERENCES course_offering(offering_id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;

-- 10. RESULT
-- Student marks ledger tied to specific exam and enrollment.
-- Composite UNIQUE prevents multiple grade entries for same student exam.
CREATE TABLE result (
    result_id INT AUTO_INCREMENT PRIMARY KEY,
    exam_id INT NOT NULL,
    enrollment_id INT NOT NULL,
    marks_obtained DECIMAL(5,2) NOT NULL,
    CONSTRAINT uk_result UNIQUE (exam_id, enrollment_id),
    CONSTRAINT chk_result_marks CHECK (marks_obtained >= 0),
    CONSTRAINT fk_result_exam FOREIGN KEY (exam_id)
        REFERENCES exam(exam_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_result_enrollment FOREIGN KEY (enrollment_id)
        REFERENCES enrollment(enrollment_id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;

-- 11. FEE_STRUCTURE (Identifying Weak Entity)
-- Department tuition schedule per semester.
-- Composite PK (dept_id, semester_no) guarantees single fee rule per semester.
CREATE TABLE fee_structure (
    dept_id INT NOT NULL,
    semester_no TINYINT NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    PRIMARY KEY (dept_id, semester_no),
    CONSTRAINT chk_fee_sem CHECK (semester_no BETWEEN 1 AND 8),
    CONSTRAINT chk_fee_amt CHECK (amount > 0),
    CONSTRAINT fk_fee_dept FOREIGN KEY (dept_id)
        REFERENCES department(dept_id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;

-- 12. FEE_PAYMENT
-- Financial payment receipts recorded for tuition installments.
-- ON DELETE RESTRICT on student_id prevents erasing financial audit records.
CREATE TABLE fee_payment (
    payment_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    semester_no TINYINT NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    paid_on DATE NOT NULL,
    mode ENUM('Cash', 'Card', 'UPI', 'Net Banking', 'Demand Draft') NOT NULL,
    receipt_no VARCHAR(50) NOT NULL,
    CONSTRAINT uk_receipt UNIQUE (receipt_no),
    CONSTRAINT chk_payment_sem CHECK (semester_no BETWEEN 1 AND 8),
    CONSTRAINT chk_payment_amt CHECK (amount > 0),
    CONSTRAINT fk_payment_student FOREIGN KEY (student_id)
        REFERENCES student(student_id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

-- 13. ADMISSION_APPLICATION
-- Prospective student intake queue before formal matriculation.
CREATE TABLE admission_application (
    application_id INT AUTO_INCREMENT PRIMARY KEY,
    applicant_name VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    dept_id INT NOT NULL,
    applied_on DATE NOT NULL,
    status ENUM('Pending', 'Approved', 'Rejected') NOT NULL DEFAULT 'Pending',
    reviewed_by INT NULL,
    reviewed_on DATETIME NULL,
    CONSTRAINT fk_app_dept FOREIGN KEY (dept_id)
        REFERENCES department(dept_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_app_reviewer FOREIGN KEY (reviewed_by)
        REFERENCES faculty(faculty_id) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB;

-- 14. APP_USER (Polymorphic Authentication Store)
-- System authentication credentials with strict polymorphic check constraint.
CREATE TABLE app_user (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('admin', 'faculty', 'student') NOT NULL,
    student_id INT NULL,
    faculty_id INT NULL,
    CONSTRAINT uk_username UNIQUE (username),
    CONSTRAINT fk_user_student FOREIGN KEY (student_id)
        REFERENCES student(student_id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_user_faculty FOREIGN KEY (faculty_id)
        REFERENCES faculty(faculty_id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT chk_user_polymorphism CHECK (
        (role = 'admin' AND student_id IS NULL AND faculty_id IS NULL) OR
        (role = 'faculty' AND student_id IS NULL AND faculty_id IS NOT NULL) OR
        (role = 'student' AND student_id IS NOT NULL AND faculty_id IS NULL)
    )
) ENGINE=InnoDB;

-- 15. AUDIT_LOG
-- Autonomous ledger tracking data modification actions (INSERT/UPDATE/DELETE).
CREATE TABLE audit_log (
    log_id INT AUTO_INCREMENT PRIMARY KEY,
    table_name VARCHAR(50) NOT NULL,
    action ENUM('INSERT', 'UPDATE', 'DELETE') NOT NULL,
    record_id INT NOT NULL,
    old_values JSON NULL,
    new_values JSON NULL,
    changed_by VARCHAR(50) NOT NULL,
    changed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;
