-- ============================================================================
-- STUDENT INFORMATION MANAGEMENT SYSTEM (SIMS) - DATABASE SECURITY ROLES & GRANTS
-- Purpose: Principle of Least Privilege role-based access control (RBAC)
-- ============================================================================

USE sims_db;

CREATE ROLE IF NOT EXISTS sims_admin;
CREATE ROLE IF NOT EXISTS sims_faculty;
CREATE ROLE IF NOT EXISTS sims_student;

-- 1. Administrator Privileges: Full execution and read/write on domain tables
GRANT SELECT, INSERT, UPDATE, DELETE ON sims_db.* TO sims_admin;
GRANT EXECUTE ON PROCEDURE sims_db.sp_enroll_student TO sims_admin;
GRANT EXECUTE ON PROCEDURE sims_db.sp_approve_admission TO sims_admin;
GRANT EXECUTE ON PROCEDURE sims_db.sp_record_payment TO sims_admin;
GRANT EXECUTE ON FUNCTION sims_db.fn_grade TO sims_admin;
GRANT EXECUTE ON FUNCTION sims_db.fn_attendance_pct TO sims_admin;
GRANT EXECUTE ON FUNCTION sims_db.fn_student_cgpa TO sims_admin;

-- 2. Faculty Privileges: Attendance, Results, View rosters & course offerings
GRANT SELECT ON sims_db.v_student_overview TO sims_faculty;
GRANT SELECT ON sims_db.v_course_offering_stats TO sims_faculty;
GRANT SELECT ON sims_db.course_offering TO sims_faculty;
GRANT SELECT ON sims_db.enrollment TO sims_faculty;
GRANT SELECT, INSERT, UPDATE ON sims_db.attendance TO sims_faculty;
GRANT SELECT, INSERT, UPDATE ON sims_db.exam TO sims_faculty;
GRANT SELECT, INSERT, UPDATE ON sims_db.result TO sims_faculty;
GRANT EXECUTE ON FUNCTION sims_db.fn_grade TO sims_faculty;
GRANT EXECUTE ON FUNCTION sims_db.fn_attendance_pct TO sims_faculty;

-- 3. Demonstration SQL role: these views are not row-level security.
-- Portal students must not receive database credentials; Flask enforces ownership.
GRANT SELECT ON sims_db.v_course_offering_stats TO sims_student;
GRANT SELECT ON sims_db.v_attendance_summary TO sims_student;
GRANT SELECT ON sims_db.v_fee_status TO sims_student;
GRANT EXECUTE ON PROCEDURE sims_db.sp_enroll_student TO sims_student;
GRANT EXECUTE ON FUNCTION sims_db.fn_grade TO sims_student;
GRANT EXECUTE ON FUNCTION sims_db.fn_attendance_pct TO sims_student;
GRANT EXECUTE ON FUNCTION sims_db.fn_student_cgpa TO sims_student;
