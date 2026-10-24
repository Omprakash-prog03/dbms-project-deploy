# STUDENT INFORMATION MANAGEMENT SYSTEM (SIMS)
## COMPREHENSIVE DBMS DESIGN SPECIFICATION & VIVA DEFENSE BLUEPRINT
**Target Level:** B.Tech Computer Science & Engineering (Graded DBMS Mini-Project)
**Audience:** External DBMS Viva Examiner & Academic Evaluation Committee

---

# EXECUTIVE SUMMARY & DESIGN PHILOSOPHY
The Student Information Management System (SIMS) is engineered strictly as a **database-first system**, where the relational database is the core intellectual property, rather than an afterthought behind an ORM. In this project, database design correctness, normalization rigor, relational constraints (PK, FK, CHECK, UNIQUE, NOT NULL), atomic transactions with row-level locks, views, triggers, stored procedures, and index execution plans take precedence over ephemeral framework sugar. The front-end application faithfully adheres to modern aesthetic standards (modeled after the Jobgio floating light dashboard), serving specifically as an interactive glass window that demonstrates, tests, and visualizes the database engine's underlying ACID mechanics.

---

# TABLE OF CONTENTS
1. [Pre-Mortem: 8 Viva Failure Modes & Mitigations](#pre-mortem-8-viva-failure-modes--mitigations)
2. [Phase 1: Requirements & System Scope](#phase-1-requirements--system-scope)
3. [Phase 2: Conceptual Design (ER Diagrams & Relationships)](#phase-2-conceptual-design-er-diagrams--relationships)
4. [Phase 3: Logical Design & Normalization Walkthrough](#phase-3-logical-design--normalization-walkthrough)
5. [Phase 4: Physical Design (MySQL 8 DDL, Triggers, Routines & Roles)](#phase-4-physical-design-mysql-8-ddl-triggers-routines--roles)
6. [Phase 5: Showcase Query Catalogue (25 Showcase Queries)](#phase-5-showcase-query-catalogue-25-showcase-queries)
7. [Phase 6: Application & UI Design (Jobgio Architecture & Wireframes)](#phase-6-application--ui-design-jobgio-architecture--wireframes)
8. [Phase 7: Implementation Plan & Pytest Verification Strategy](#phase-7-implementation-plan--pytest-verification-strategy)

---

# PRE-MORTEM: 8 VIVA FAILURE MODES & MITIGATIONS

Examiners in a university DBMS viva routinely probe system boundaries with edge cases, concurrency hazards, and normalization traps. Below are the 8 fatal pitfalls identified during system architectural review, coupled with their concrete, battle-tested mitigations:

| # | Viva Trap / Weakness | Risk / Failure Mode | Concrete Engineering Mitigation |
|---|---|---|---|
| **1** | **Tables Violating 2NF/3NF** | Storing `dept_name` inside `student` or deriving totals (`total_marks`, `gpa`) as persistent columns without normalization. Viva examiners immediately flag transitive dependencies and update anomalies. | Fully decomposed into 3NF/BCNF. `student` retains only `dept_id FK`. CGPA and grades are calculated dynamically via stored function `fn_student_cgpa()` and views. The only denormalized scalar (`enrolled_count`) is explicitly justified and maintained via transactional triggers. |
| **2** | **Many-to-Many Modelled Wrongly** | Modeling the `student`-`course` relationship with comma-separated IDs or embedding `student_id` in `course` (restricting a course to one student). | Explicit associative junction entity `enrollment(enrollment_id, student_id, offering_id, enroll_date, status)` with composite unique constraint `UNIQUE(student_id, offering_id)` to forbid duplicate registrations while preserving history. |
| **3** | **Inconsistent FK Delete Rules** | Using blind `CASCADE` on academic histories (deleting a course wipes out historical transcripts) or orphan rows left by accidental `SET NULL`. | Every foreign key has an explicitly chosen, documented policy: `RESTRICT` on courses, enrollments, exams, and results to preserve academic integrity; `CASCADE` strictly on existence-dependent children (`guardian`); `SET NULL` on nullable leadership pointers (`hod_faculty_id`, `reviewed_by`). |
| **4** | **Race Condition on Last Seat (Overselling)** | Two concurrent students enrolling into an offering with 1 remaining seat simultaneously, both reading `enrolled_count < capacity` and both committing, exceeding physical capacity. | Implemented in stored procedure `sp_enroll_student` wrapped in an explicit transaction utilizing pessimistic row-level locking: `SELECT capacity, enrolled_count FROM course_offering WHERE offering_id = ? FOR UPDATE;` backed by trigger `trg_enrollment_before_insert` as a defense-in-depth gate. |
| **5** | **SQL Injection via Search / Sort / Filter** | Dynamic query concatenation in Flask (e.g. `WHERE name LIKE '%" + q + "%'` or `ORDER BY " + sort_col`), allowing examiners to bypass authentication or drop tables. | Strict two-layer defense: All filtering and criteria parameters use MySQL parameterized placeholders (`%s`). All dynamic sort/filter column names and directions are validated against a strict Python server-side allowlist (`ALLOWED_SORT_COLUMNS`); non-matching keys trigger an immediate HTTP 400 rejection. |
| **6** | **Business Rules Enforced Only in UI** | Relying on HTML5 `required` or JS `if (marks > max)` while the database accepts raw invalid inserts from SQL clients. | True database-level integrity: Database `CHECK` constraints on ranges (`marks_obtained >= 0`, `credits BETWEEN 1 AND 6`, `salary > 0`, `dob <= admission_date - INTERVAL 15 YEAR`), `ENUM` datatypes, and `BEFORE INSERT/UPDATE` triggers that raise `SQLSTATE '45000'` exceptions if rules are breached. |
| **7** | **Slow Dashboard Queries (N+1 Problem)** | Iterating over 500+ students in Python and issuing individual `SELECT` queries for their course count and fee dues, causing sluggish response times and database exhaustion. | All dashboard metrics, status pills, and tables are computed in single set-based SQL joins and indexed aggregated views (`v_student_overview`, `v_fee_status`). Composite B-Tree indexes on `(offering_id, student_id)` and `(dept_id, status)` ensure index-only scans with sub-millisecond execution plans demonstrated live via `EXPLAIN`. |
| **8** | **Hardcoded Numbers in UI** | Templates containing hardcoded strings like "500 Total Students" or mock chart values that do not react to database inserts during live testing. | Every KPI card, chart datapoint, and status pill is fed dynamically from live SQL aggregate endpoints (`/api/dashboard/stats`, `/api/dashboard/chart`) backed by views. An interactive "Show SQL" inspection pill on every UI screen exposes the exact live query and parameters used to render the data. |

---

# PHASE 1: REQUIREMENTS & SYSTEM SCOPE

## 1.1 System Actors & Role Permissions
The system defines three core human roles, enforced at both the application gateway and the MySQL database user privilege layer:

1. **Academic Administrator (`sims_admin`)**:
   - Manages institutional master data: Departments, Faculty profiles, Course catalogs, Fee structures, and Semester offerings.
   - Evaluates admission applications (`sp_approve_admission`), automatically provisioning student profiles and system user credentials.
   - Monitors financial collections, identifies fee defaulters, oversees audit trail logs, and reviews database query performance.

2. **Faculty Instructor (`sims_faculty`)**:
   - Reviews assigned course offerings and enrolled student rosters.
   - Records and updates daily classroom attendance (`Present`, `Absent`, `Late`) within an atomic transaction.
   - Schedules evaluations (Internal, Midterm, Final) and inputs student marks with automated trigger validation against maximum marks.
   - Views performance analytics, grade distributions, and attendance percentages for their specific classes.

3. **Student Scholar (`sims_student`)**:
   - Accesses a personalized academic portal: Enrolled courses, timetable schedules, attendance percentages, and published exam grades.
   - Self-registers for open course offerings subject to semester eligibility and real-time seat availability.
   - Inspects fee ledgers, calculates semester dues, and reviews past payment receipts.

---

## 1.2 Functional Modules & Business Rules

### A. Admissions & Matriculation
- **Rule 1.1 (Application Validation)**: An applicant must provide a valid email and phone number and choose an existing department.
- **Rule 1.2 (Atomic Admission Approval)**: When an application is approved via `sp_approve_admission`, the system must in a single atomic transaction:
  1. Update application status to `'Approved'` and record `reviewed_by` and `reviewed_on`.
  2. Generate a standard institutional Roll Number (e.g., `YYDEPTXXX`, such as `26CSE001`).
  3. Insert the candidate into `student` with status `'Active'`.
  4. Create an entry in `app_user` with a hashed default password and role `'student'`.
  5. Record the administrative action in `audit_log`.

### B. Student Profiles & Demographics
- **Rule 2.1 (Age Restriction)**: Students must be at least 15 years of age on their admission date (`CHECK (dob <= admission_date - INTERVAL 15 YEAR)`).
- **Rule 2.2 (Department Integrity)**: Every student must be affiliated with exactly one department. Deleting a department that contains students is strictly forbidden (`ON DELETE RESTRICT`).
- **Rule 2.3 (Guardian Dependency)**: Guardian records represent emergency contacts; if a student is purged, guardian records are cascade deleted (`ON DELETE CASCADE`).

### C. Courses, Offerings & Workload
- **Rule 3.1 (Course Credits)**: Catalog course credits are constrained between 1 and 6 (`CHECK (credits BETWEEN 1 AND 6)`).
- **Rule 3.2 (Offering Uniqueness)**: A catalog course cannot be offered more than once within the same academic year and term (`UNIQUE(course_id, academic_year, term)`).
- **Rule 3.3 (Instructor Assignment)**: Every course offering must be assigned to an active faculty member belonging to an academic department.

### D. Course Enrollment & Capacity Management
- **Rule 4.1 (Single Enrollment)**: A student can register for an offering at most once (`UNIQUE(student_id, offering_id)`).
- **Rule 4.2 (Capacity Barrier & Concurrency)**: Enrollments must not exceed the specified offering capacity. Concurrent enrollment attempts on the last available seat must serialize using `SELECT ... FOR UPDATE` row-level locks.
- **Rule 4.3 (Active Status Prerequisite)**: Only students with `status = 'Active'` may enroll; suspended or dropped students are rejected at the trigger level.

### E. Attendance Tracking
- **Rule 5.1 (Daily Uniqueness)**: A student cannot have more than one attendance log entry for the same enrollment on the same calendar date (`UNIQUE(enrollment_id, class_date)`).
- **Rule 5.2 (Valid Enrollment State)**: Attendance cannot be marked for an enrollment whose status is `'Dropped'` (`trg_attendance_before_insert`).

### F. Examinations, Marks & Grading
- **Rule 6.1 (Exam Maximum Marks)**: Scheduled exams must specify maximum marks strictly greater than zero (`CHECK (max_marks > 0)`).
- **Rule 6.2 (Marks Ceiling)**: Marks obtained cannot be negative and cannot exceed the exam's configured maximum marks (`trg_result_before_insert_update`).
- **Rule 6.3 (Single Score per Exam)**: A student receives at most one recorded result per scheduled exam (`UNIQUE(exam_id, enrollment_id)`).

### G. Fee Accounting & Installment Controls
- **Rule 7.1 (Fee Schedule Determinism)**: Each department sets a tuition fee per semester (`PRIMARY KEY (dept_id, semester_no)`).
- **Rule 7.2 (Receipt Uniqueness)**: Every payment receipt number must be globally unique (`UNIQUE(receipt_no)`).
- **Rule 7.3 (Overpayment Prevention)**: Cumulative payments for a given student and semester must not exceed the total fee stipulated by the fee structure for that student's department (`sp_record_payment`).

---

## 1.3 Architectural Assumptions
- *Assumption 1*: The academic calendar consists of three terms per year: `Fall`, `Spring`, and `Summer`.
- *Assumption 2*: Academic years are formatted as 9-character strings (e.g. `'2025-2026'`).
- *Assumption 3*: Standard semester progression runs from Semester 1 through Semester 8.
- *Assumption 4*: Password hashes utilize standard PBKDF2/bcrypt formatted strings requiring a `VARCHAR(255)` field.
- *Assumption 5*: All monetary figures represent standard local currency units stored using `DECIMAL(10,2)` to prevent floating-point rounding errors.

---

# PHASE 2: CONCEPTUAL DESIGN (ER DIAGRAMS & RELATIONSHIPS)

## 2.1 Complete Mermaid Entity-Relationship Diagram

`mermaid
erDiagram
    DEPARTMENT ||--o{ FACULTY : "employs"
    DEPARTMENT ||--o{ STUDENT : "enrolls"
    DEPARTMENT ||--o{ COURSE : "offers"
    DEPARTMENT ||--o{ FEE_STRUCTURE : "specifies"
    DEPARTMENT ||--o{ ADMISSION_APPLICATION : "receives"
    DEPARTMENT |o--o| FACULTY : "headed_by (HoD)"

    FACULTY ||--o{ COURSE_OFFERING : "instructs"
    FACULTY |o--o| APP_USER : "authenticates_as"
    FACULTY |o--o{ ADMISSION_APPLICATION : "reviews"

    STUDENT ||--o{ GUARDIAN : "has"
    STUDENT ||--o{ ENROLLMENT : "registers"
    STUDENT ||--o{ FEE_PAYMENT : "pays"
    STUDENT |o--o| APP_USER : "authenticates_as"

    COURSE ||--o{ COURSE_OFFERING : "instantiated_as"

    COURSE_OFFERING ||--o{ ENROLLMENT : "contains"
    COURSE_OFFERING ||--o{ EXAM : "schedules"

    ENROLLMENT ||--o{ ATTENDANCE : "tracks"
    ENROLLMENT ||--o{ RESULT : "evaluates"

    EXAM ||--o{ RESULT : "grades"

    DEPARTMENT {
        int dept_id PK
        string dept_code UK
        string dept_name UK
        int hod_faculty_id FK
        int established_year
    }

    FACULTY {
        int faculty_id PK
        string first_name
        string last_name
        string email UK
        string phone
        int dept_id FK
        string designation
        date hire_date
        decimal salary
        string status
    }

    STUDENT {
        int student_id PK
        string roll_no UK
        string first_name
        string last_name
        string email UK
        string phone
        date dob
        string gender
        string address
        int dept_id FK
        date admission_date
        int current_semester
        string status
        string photo_url
    }

    GUARDIAN {
        int guardian_id PK
        int student_id FK
        string name
        string relation
        string phone
    }

    COURSE {
        int course_id PK
        string course_code UK
        string title
        int credits
        int dept_id FK
        int semester_no
    }

    COURSE_OFFERING {
        int offering_id PK
        int course_id FK
        int faculty_id FK
        string academic_year
        string term
        int capacity
        int enrolled_count
    }

    ENROLLMENT {
        int enrollment_id PK
        int student_id FK
        int offering_id FK
        date enroll_date
        string status
    }

    ATTENDANCE {
        int attendance_id PK
        int enrollment_id FK
        date class_date
        string status
    }

    EXAM {
        int exam_id PK
        int offering_id FK
        string exam_type
        decimal max_marks
        date exam_date
    }

    RESULT {
        int result_id PK
        int exam_id FK
        int enrollment_id FK
        decimal marks_obtained
    }

    FEE_STRUCTURE {
        int dept_id PK,FK
        int semester_no PK
        decimal amount
    }

    FEE_PAYMENT {
        int payment_id PK
        int student_id FK
        int semester_no
        decimal amount
        date paid_on
        string mode
        string receipt_no UK
    }

    ADMISSION_APPLICATION {
        int application_id PK
        string applicant_name
        string email
        string phone
        int dept_id FK
        date applied_on
        string status
        int reviewed_by FK
        datetime reviewed_on
    }

    APP_USER {
        int user_id PK
        string username UK
        string password_hash
        string role
        int student_id FK
        int faculty_id FK
    }

    AUDIT_LOG {
        int log_id PK
        string table_name
        string action
        int record_id
        json old_values
        json new_values
        string changed_by
        datetime changed_at
    }
```



---

## 2.2 Complete ASCII Entity-Relationship Diagram

```
+-----------------------------------------------------------------------------------------------------------------+
|                                          SIMS CONCEPTUAL ER SCHEMA                                              |
+-----------------------------------------------------------------------------------------------------------------+

                      [ADMISSION_APPLICATION]
                                 | (1)
                                 | reviewed_by (0..1)
                                 v
   +------------------------ [FACULTY] <-------------------+ (0..1)
   |                             |                         |
   |                             | (1) employs             | headed_by
   |                             v                         | (HoD)
   |                     +---------------+ (1)             |
   |                     |  DEPARTMENT   |-----------------+
   |                     +---------------+
   |                      | (1)      | (1)
   |          offers (1)  |          | specifies (1)
   |                      v          v
   |                  [COURSE]    [FEE_STRUCTURE] (Identifying Weak Entity)
   |                      | (1)
   |       instantiated   |
   |       as             v
   +---------------> [COURSE_OFFERING] <-------------------+
                          | (1)                            |
                          |                                |
         contains (1)     |                                | schedules (1)
                          v                                |
                    [ENROLLMENT] (M:N Junction)            |
                     | (1)       | (1)                     v
        tracks (1)   |           | evaluated_in (1)      [EXAM]
                     v           v                         |
               [ATTENDANCE]   [RESULT] <-------------------+ (1) scores
                                 ^
                                 | (1)
  [STUDENT] ---------------------+ (registers)
    |   |
    |   +-----------------------> [GUARDIAN] (Existence-dependent Weak Entity)
    |        has (1)
    +---------------------------> [FEE_PAYMENT] (pays)
             makes (1)

  [APP_USER]   --> Authenticates credentials; mutually exclusive pointer to STUDENT or FACULTY
  [AUDIT_LOG]  --> System autonomous ledger logging DML operations with JSON state payloads
```

---

## 2.3 Conceptual Entities & Attribute Roster

1. **DEPARTMENT**: Identifies the academic department.
   - Attributes: `dept_id` (PK), `dept_code` (UK), `dept_name` (UK), `hod_faculty_id` (FK, Nullable), `established_year`.
2. **FACULTY**: Academic instructional staff.
   - Attributes: `faculty_id` (PK), `first_name`, `last_name`, `email` (UK), `phone`, `dept_id` (FK), `designation`, `hire_date`, `salary`, `status`.
3. **STUDENT**: Matriculated students.
   - Attributes: `student_id` (PK), `roll_no` (UK), `first_name`, `last_name`, `email` (UK), `phone`, `dob`, `gender`, `address`, `dept_id` (FK), `admission_date`, `current_semester`, `status`, `photo_url`.
4. **GUARDIAN**: Emergency contacts and parents (Weak Entity).
   - Attributes: `guardian_id` (PK), `student_id` (FK), `name`, `relation`, `phone`.
5. **COURSE**: Catalog of educational courses.
   - Attributes: `course_id` (PK), `course_code` (UK), `title`, `credits`, `dept_id` (FK), `semester_no`.
6. **COURSE_OFFERING**: Term-specific instance of a course.
   - Attributes: `offering_id` (PK), `course_id` (FK), `faculty_id` (FK), `academic_year`, `term`, `capacity`, `enrolled_count` (denormalized, trigger-managed).
7. **ENROLLMENT**: Associative entity linking students and offerings.
   - Attributes: `enrollment_id` (PK), `student_id` (FK), `offering_id` (FK), `enroll_date`, `status`.
8. **ATTENDANCE**: Daily presence logs.
   - Attributes: `attendance_id` (PK), `enrollment_id` (FK), `class_date`, `status`.
9. **EXAM**: Scheduled academic assessment.
   - Attributes: `exam_id` (PK), `offering_id` (FK), `exam_type`, `max_marks`, `exam_date`.
10. **RESULT**: Evaluation scores obtained by enrolled students.
    - Attributes: `result_id` (PK), `exam_id` (FK), `enrollment_id` (FK), `marks_obtained`.
11. **FEE_STRUCTURE**: Departmental semester tuition matrix (Weak Entity).
    - Attributes: `dept_id` (PK, FK), `semester_no` (PK), `amount`.
12. **FEE_PAYMENT**: Individual payment transaction ledger.
    - Attributes: `payment_id` (PK), `student_id` (FK), `semester_no`, `amount`, `paid_on`, `mode`, `receipt_no` (UK).
13. **ADMISSION_APPLICATION**: Pre-matriculation admissions pipeline.
    - Attributes: `application_id` (PK), `applicant_name`, `email`, `phone`, `dept_id` (FK), `applied_on`, `status`, `reviewed_by` (FK, Nullable), `reviewed_on`.
14. **APP_USER**: System security and authentication credentials.
    - Attributes: `user_id` (PK), `username` (UK), `password_hash`, `role`, `student_id` (FK, Nullable), `faculty_id` (FK, Nullable).
15. **AUDIT_LOG**: Administrative and financial security ledger.
    - Attributes: `log_id` (PK), `table_name`, `action`, `record_id`, `old_values` (JSON), `new_values` (JSON), `changed_by`, `changed_at`.

---

## 2.4 Detailed Relationship Analysis & Cardinalities

Each relationship is academically justified below with explicit cardinality and participation constraints:

1. **`DEPARTMENT` employs `FACULTY` (1:N)**:
   - *Cardinality*: 1 to Many. One department employs zero or many faculty members; each faculty member belongs to exactly one department.
   - *Participation*: `DEPARTMENT` is partial (a newly founded department may not yet have hired faculty); `FACULTY` is total/mandatory (every faculty member must be assigned to an academic department).
   - *Justification*: Prevents unattached faculty in institutional reporting and payroll processing.

2. **`DEPARTMENT` headed_by `FACULTY` (1:1)**:
   - *Cardinality*: 1 to 1. A department has at most one Head of Department (HoD); a faculty member heads at most one department.
   - *Participation*: Both are partial (a department may have a temporarily vacant HoD post; most faculty members are not HoDs).
   - *Justification*: Models departmental governance without circular dependency locks. Implemented via nullable `department.hod_faculty_id` with `ON DELETE SET NULL`.

3. **`DEPARTMENT` enrolls `STUDENT` (1:N)**:
   - *Cardinality*: 1 to Many. A department enrolls zero or many students; each student is matriculated into exactly one major department.
   - *Participation*: `DEPARTMENT` is partial; `STUDENT` is total (a student must have an academic major).
   - *Justification*: Establishes degree requirements, graduation auditing, and cohort tuition liabilities.

4. **`STUDENT` has `GUARDIAN` (1:N)**:
   - *Cardinality*: 1 to Many. A student has zero, one, or more emergency contacts/guardians; each guardian record belongs to one student.
   - *Participation*: `STUDENT` is partial; `GUARDIAN` is total.
   - *Weak Entity Justification*: `GUARDIAN` is an existence-dependent weak entity because an emergency contact cannot exist without the associated student. Deleting a student cascades (`ON DELETE CASCADE`) to their guardians.

5. **`DEPARTMENT` offers `COURSE` (1:N)**:
   - *Cardinality*: 1 to Many. A department designs and offers many courses; each catalog course is owned by one department.
   - *Participation*: `DEPARTMENT` is partial; `COURSE` is total.
   - *Justification*: Organizes institutional curriculum and prevents orphan courses if departments are audited.

6. **`COURSE` instantiated_as `COURSE_OFFERING` (1:N)**:
   - *Cardinality*: 1 to Many. A syllabus course can be scheduled across multiple terms and academic years; each offering is an instance of one course.
   - *Participation*: `COURSE` is partial (some catalog courses are not offered every term); `COURSE_OFFERING` is total.
   - *Justification*: Decouples static syllabus specifications (title, credits) from dynamic term scheduling (instructor, classroom seat capacity, term).

7. **`FACULTY` instructs `COURSE_OFFERING` (1:N)**:
   - *Cardinality*: 1 to Many. A faculty member can instruct multiple course offerings per term; each offering has a designated lead instructor.
   - *Participation*: `FACULTY` is partial (professors on sabbatical or research may have no active offerings); `COURSE_OFFERING` is total.
   - *Justification*: Maps teaching workload and grants grading authorization to the designated faculty member.

8. **`STUDENT` registers `COURSE_OFFERING` via `ENROLLMENT` (M:N)**:
   - *Cardinality*: Many to Many resolved via associative junction table `ENROLLMENT`.
   - *Participation*: `STUDENT` is partial (new students in orientation have 0 enrollments); `COURSE_OFFERING` is partial (a newly opened elective starts with 0 enrollments).
   - *Justification*: A junction table is mandatory in relational theory to resolve many-to-many cardinality and attach attributes specific to the interaction (`enroll_date`, `status`).

9. **`ENROLLMENT` tracks `ATTENDANCE` (1:N)**:
   - *Cardinality*: 1 to Many. An enrollment accumulates daily attendance entries across the semester; each attendance record belongs to one student enrollment.
   - *Participation*: `ENROLLMENT` is partial (at day 0, no attendance is logged); `ATTENDANCE` is total.
   - *Justification*: Enables granular day-by-day attendance auditing, calculation of eligibility thresholds, and viva defense queries.

10. **`COURSE_OFFERING` schedules `EXAM` (1:N)**:
    - *Cardinality*: 1 to Many. An offering conducts multiple assessments (Internal, Midterm, Final); an exam belongs to one offering.
    - *Participation*: `COURSE_OFFERING` is partial; `EXAM` is total.
    - *Justification*: Encapsulates evaluation schedules, syllabus coverage milestones, and exam weightages per offering.

11. **`EXAM` & `ENROLLMENT` evaluate `RESULT` (Ternary decomposed into Binary)**:
    - *Cardinality*: 1:N from `EXAM` and 1:N from `ENROLLMENT` into `RESULT`.
    - *Participation*: Partial from both parents; total for `RESULT`.
    - *Justification*: Links the specific examination milestone to the student's enrollment record, strictly enforcing `UNIQUE(exam_id, enrollment_id)`.

12. **`DEPARTMENT` specifies `FEE_STRUCTURE` (1:N)**:
    - *Cardinality*: 1 to Many. A department defines tuition amounts across 8 semesters.
    - *Participation*: `DEPARTMENT` is partial; `FEE_STRUCTURE` is total.
    - *Weak Entity Justification*: Identifying weak entity using composite key `(dept_id, semester_no)`, relying on `DEPARTMENT` for identity.

13. **`STUDENT` pays `FEE_PAYMENT` (1:N)**:
    - *Cardinality*: 1 to Many. A student makes multiple payments over their degree; each payment belongs to one student.
    - *Participation*: `STUDENT` is partial; `FEE_PAYMENT` is total.
    - *Justification*: Provides an immutable financial ledger tracking dates, amounts, transaction modes, and unique receipt numbers.

14. **`ADMISSION_APPLICATION` reviewed_by `FACULTY` (0..1:N)**:
    - *Cardinality*: Optional 1 to Many. An application is initially unreviewed (`reviewed_by IS NULL`), and subsequently approved/rejected by a faculty reviewer.
    - *Participation*: `ADMISSION_APPLICATION` is partial; `FACULTY` is partial.
    - *Justification*: Implements role separation between public applicant submissions and administrative faculty vetting.

15. **`APP_USER` authenticates `STUDENT` / `FACULTY` (1:1 Optional)**:
    - *Cardinality*: 1 to 1 mutually exclusive optional.
    - *Participation*: Partial on all sides.
    - *Justification*: Centralizes authentication credentials (username, password hash) while maintaining clean polymorphic linkage to either a student or a faculty profile via CHECK constraints.

---

# PHASE 3: LOGICAL DESIGN & NORMALIZATION WALKTHROUGH

## 3.1 Relational Schema Specification
The relational schema is formalized below with complete primary, foreign, unique, and check constraints:

* **`department`** (
    **`dept_id`**: INT PK,
    `dept_code`: VARCHAR(10) UNIQUE NOT NULL,
    `dept_name`: VARCHAR(100) UNIQUE NOT NULL,
    *`hod_faculty_id`*: INT NULL FK $\to$ `faculty.faculty_id`,
    `established_year`: INT NOT NULL CHECK (`established_year` $\ge$ 1900)
  )

* **`faculty`** (
    **`faculty_id`**: INT PK,
    `first_name`: VARCHAR(50) NOT NULL,
    `last_name`: VARCHAR(50) NOT NULL,
    `email`: VARCHAR(100) UNIQUE NOT NULL,
    `phone`: VARCHAR(20) NOT NULL,
    *`dept_id`*: INT NOT NULL FK $\to$ `department.dept_id`,
    `designation`: ENUM('Professor', 'Associate Professor', 'Assistant Professor', 'Lecturer') NOT NULL,
    `hire_date`: DATE NOT NULL,
    `salary`: DECIMAL(10,2) NOT NULL CHECK (`salary` > 0),
    `status`: ENUM('Active', 'On Leave', 'Resigned', 'Retired') NOT NULL DEFAULT 'Active'
  )

* **`student`** (
    **`student_id`**: INT PK,
    `roll_no`: VARCHAR(20) UNIQUE NOT NULL,
    `first_name`: VARCHAR(50) NOT NULL,
    `last_name`: VARCHAR(50) NOT NULL,
    `email`: VARCHAR(100) UNIQUE NOT NULL,
    `phone`: VARCHAR(20) NOT NULL,
    `dob`: DATE NOT NULL,
    `gender`: ENUM('Male', 'Female', 'Other') NOT NULL,
    `address`: TEXT NOT NULL,
    *`dept_id`*: INT NOT NULL FK $\to$ `department.dept_id`,
    `admission_date`: DATE NOT NULL,
    `current_semester`: TINYINT NOT NULL CHECK (`current_semester` BETWEEN 1 AND 8),
    `status`: ENUM('Active', 'Graduated', 'Suspended', 'Dropped') NOT NULL DEFAULT 'Active',
    `photo_url`: VARCHAR(255) NULL,
    CHECK (`dob` $\le$ `admission_date` - INTERVAL 15 YEAR)
  )

* **`guardian`** (
    **`guardian_id`**: INT PK,
    *`student_id`*: INT NOT NULL FK $\to$ `student.student_id` ON DELETE CASCADE,
    `name`: VARCHAR(100) NOT NULL,
    `relation`: VARCHAR(50) NOT NULL,
    `phone`: VARCHAR(20) NOT NULL
  )

* **`course`** (
    **`course_id`**: INT PK,
    `course_code`: VARCHAR(20) UNIQUE NOT NULL,
    `title`: VARCHAR(100) NOT NULL,
    `credits`: TINYINT NOT NULL CHECK (`credits` BETWEEN 1 AND 6),
    *`dept_id`*: INT NOT NULL FK $\to$ `department.dept_id`,
    `semester_no`: TINYINT NOT NULL CHECK (`semester_no` BETWEEN 1 AND 8)
  )

* **`course_offering`** (
    **`offering_id`**: INT PK,
    *`course_id`*: INT NOT NULL FK $\to$ `course.course_id`,
    *`faculty_id`*: INT NOT NULL FK $\to$ `faculty.faculty_id`,
    `academic_year`: VARCHAR(9) NOT NULL,
    `term`: ENUM('Fall', 'Spring', 'Summer') NOT NULL,
    `capacity`: SMALLINT NOT NULL CHECK (`capacity` > 0),
    `enrolled_count`: SMALLINT NOT NULL DEFAULT 0 CHECK (`enrolled_count` $\ge$ 0),
    UNIQUE (`course_id`, `academic_year`, `term`)
  )

* **`enrollment`** (
    **`enrollment_id`**: INT PK,
    *`student_id`*: INT NOT NULL FK $\to$ `student.student_id`,
    *`offering_id`*: INT NOT NULL FK $\to$ `course_offering.offering_id`,
    `enroll_date`: DATE NOT NULL,
    `status`: ENUM('Enrolled', 'Dropped', 'Completed') NOT NULL DEFAULT 'Enrolled',
    UNIQUE (`student_id`, `offering_id`)
  )

* **`attendance`** (
    **`attendance_id`**: INT PK,
    *`enrollment_id`*: INT NOT NULL FK $\to$ `enrollment.enrollment_id` ON DELETE CASCADE,
    `class_date`: DATE NOT NULL,
    `status`: ENUM('Present', 'Absent', 'Late') NOT NULL,
    UNIQUE (`enrollment_id`, `class_date`)
  )

* **`exam`** (
    **`exam_id`**: INT PK,
    *`offering_id`*: INT NOT NULL FK $\to$ `course_offering.offering_id`,
    `exam_type`: ENUM('Internal', 'Midterm', 'Final') NOT NULL,
    `max_marks`: DECIMAL(5,2) NOT NULL CHECK (`max_marks` > 0),
    `exam_date`: DATE NOT NULL,
    UNIQUE (`offering_id`, `exam_type`)
  )

* **`result`** (
    **`result_id`**: INT PK,
    *`exam_id`*: INT NOT NULL FK $\to$ `exam.exam_id`,
    *`enrollment_id`*: INT NOT NULL FK $\to$ `enrollment.enrollment_id` ON DELETE CASCADE,
    `marks_obtained`: DECIMAL(5,2) NOT NULL CHECK (`marks_obtained` $\ge$ 0),
    UNIQUE (`exam_id`, `enrollment_id`)
  )

* **`fee_structure`** (
    **`dept_id`**: INT NOT NULL FK $\to$ `department.dept_id`,
    **`semester_no`**: TINYINT NOT NULL CHECK (`semester_no` BETWEEN 1 AND 8),
    `amount`: DECIMAL(10,2) NOT NULL CHECK (`amount` > 0),
    PRIMARY KEY (`dept_id`, `semester_no`)
  )

* **`fee_payment`** (
    **`payment_id`**: INT PK,
    *`student_id`*: INT NOT NULL FK $\to$ `student.student_id`,
    `semester_no`: TINYINT NOT NULL CHECK (`semester_no` BETWEEN 1 AND 8),
    `amount`: DECIMAL(10,2) NOT NULL CHECK (`amount` > 0),
    `paid_on`: DATE NOT NULL,
    `mode`: ENUM('Cash', 'Card', 'UPI', 'Net Banking', 'Demand Draft') NOT NULL,
    `receipt_no`: VARCHAR(50) UNIQUE NOT NULL
  )

* **`admission_application`** (
    **`application_id`**: INT PK,
    `applicant_name`: VARCHAR(100) NOT NULL,
    `email`: VARCHAR(100) NOT NULL,
    `phone`: VARCHAR(20) NOT NULL,
    *`dept_id`*: INT NOT NULL FK $\to$ `department.dept_id`,
    `applied_on`: DATE NOT NULL,
    `status`: ENUM('Pending', 'Approved', 'Rejected') NOT NULL DEFAULT 'Pending',
    *`reviewed_by`*: INT NULL FK $\to$ `faculty.faculty_id` ON DELETE SET NULL,
    `reviewed_on`: DATETIME NULL
  )

* **`app_user`** (
    **`user_id`**: INT PK,
    `username`: VARCHAR(50) UNIQUE NOT NULL,
    `password_hash`: VARCHAR(255) NOT NULL,
    `role`: ENUM('admin', 'faculty', 'student') NOT NULL,
    *`student_id`*: INT NULL FK $\to$ `student.student_id` ON DELETE CASCADE,
    *`faculty_id`*: INT NULL FK $\to$ `faculty.faculty_id` ON DELETE CASCADE,
    CHECK (
      (`role` = 'admin' AND `student_id` IS NULL AND `faculty_id` IS NULL) OR
      (`role` = 'faculty' AND `student_id` IS NULL AND `faculty_id` IS NOT NULL) OR
      (`role` = 'student' AND `student_id` IS NOT NULL AND `faculty_id` IS NULL)
    )
  )

* **`audit_log`** (
    **`log_id`**: INT PK AUTO_INCREMENT,
    `table_name`: VARCHAR(50) NOT NULL,
    `action`: ENUM('INSERT', 'UPDATE', 'DELETE') NOT NULL,
    `record_id`: INT NOT NULL,
    `old_values`: JSON NULL,
    `new_values`: JSON NULL,
    `changed_by`: VARCHAR(50) NOT NULL,
    `changed_at`: TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
  )

---

## 3.2 Formal Normalization Walkthrough (UNF $\to$ 1NF $\to$ 2NF $\to$ 3NF $\to$ BCNF)

### Step 0: The Unnormalized Form (UNF)
Consider an unnormalized universal table `UNF_STUDENT_COURSE_RECORDS`:
```
(roll_no, student_name, student_email, student_dob, dept_code, dept_name, hod_name,
 {course_code, course_title, academic_year, term, faculty_email, faculty_name,
  {exam_type, max_marks, marks_obtained}},
 {guardian_name, guardian_relation, guardian_phone})
```
- **Violations**: Multi-valued attributes (nested sets of courses, evaluations, and guardians).
- **Anomalies**: Cannot store a course without a student (Insertion); deleting a student deletes course information (Deletion); updating department name requires modifying hundreds of records (Update).

### Step 1: First Normal Form (1NF)
- **Action**: Eliminate all repeating groups and arrays by flattening rows and separating independent multi-valued dependencies (such as guardians) into their own relation.
- **Resulting Flattened Relation**:
  `R_1NF (roll_no, student_name, student_email, student_dob, dept_code, dept_name, hod_name, course_code, course_title, academic_year, term, faculty_email, faculty_name, exam_type, max_marks, marks_obtained)`
- **Candidate Key**: `{roll_no, course_code, academic_year, term, exam_type}`
- **Identified Functional Dependencies (FDs)**:
  - $FD_1$: `roll_no` $\to$ `student_name`, `student_email`, `student_dob`, `dept_code`
  - $FD_2$: `dept_code` $\to$ `dept_name`, `hod_name`
  - $FD_3$: `course_code` $\to$ `course_title`, `dept_code`
  - $FD_4$: `course_code, academic_year, term` $\to$ `faculty_email`
  - $FD_5$: `faculty_email` $\to$ `faculty_name`
  - $FD_6$: `course_code, academic_year, term, exam_type` $\to$ `max_marks`
  - $FD_7$: `roll_no, course_code, academic_year, term, exam_type` $\to$ `marks_obtained`

### Step 2: Second Normal Form (2NF)
- **Definition Check**: A relation is in 2NF if it is in 1NF and no non-prime attribute is partially dependent on any candidate key.
- **Violations Identified in 1NF**:
  - $FD_1$ depends only on `roll_no` (proper subset of composite key).
  - $FD_3$ depends only on `course_code`.
  - $FD_4$ depends only on `(course_code, academic_year, term)`.
  - $FD_6$ depends only on `(course_code, academic_year, term, exam_type)`.
- **Decomposition**:
  1. `R_STUDENT (roll_no, student_name, student_email, student_dob, dept_code, dept_name, hod_name)` [Key: `roll_no`]
  2. `R_COURSE (course_code, course_title, dept_code)` [Key: `course_code`]
  3. `R_OFFERING (course_code, academic_year, term, faculty_email, faculty_name)` [Key: `(course_code, academic_year, term)`]
  4. `R_EXAM (course_code, academic_year, term, exam_type, max_marks)` [Key: `(course_code, academic_year, term, exam_type)`]
  5. `R_RESULT (roll_no, course_code, academic_year, term, exam_type, marks_obtained)` [Key: `(roll_no, course_code, academic_year, term, exam_type)`]
- **Status**: Every non-prime attribute now depends on the full primary key of its relation. **2NF Satisfied.**

### Step 3: Third Normal Form (3NF)
- **Definition Check**: A relation is in 3NF if it is in 2NF and no non-prime attribute is transitively dependent on a primary key ($X \to Y \to Z$).
- **Violations Identified in 2NF**:
  - In `R_STUDENT`: `roll_no` $\to$ `dept_code` and `dept_code` $\to$ `dept_name, hod_name`. Therefore, `roll_no` $\to$ `dept_name` is a transitive dependency through non-superkey `dept_code`.
  - In `R_OFFERING`: `(course_code, academic_year, term)` $\to$ `faculty_email` and `faculty_email` $\to$ `faculty_name`. This is a transitive dependency through `faculty_email`.
- **Decomposition**:
  1. `DEPARTMENT (dept_code, dept_name, hod_name)` [Key: `dept_code`]
  2. `STUDENT (roll_no, student_name, student_email, student_dob, dept_code FK)` [Key: `roll_no`]
  3. `FACULTY (faculty_email, faculty_name, dept_code FK)` [Key: `faculty_email`]
  4. `COURSE (course_code, course_title, dept_code FK)` [Key: `course_code`]
  5. `COURSE_OFFERING (offering_id PK, course_code FK, academic_year, term, faculty_email FK)`
  6. `ENROLLMENT (enrollment_id PK, roll_no FK, offering_id FK)`
  7. `EXAM (exam_id PK, offering_id FK, exam_type, max_marks)`
  8. `RESULT (result_id PK, exam_id FK, enrollment_id FK, marks_obtained)`
- **Status**: Transitive dependencies eliminated. Every non-key attribute depends directly on the primary key. **3NF Satisfied.**

### Step 4: Boyce-Codd Normal Form (BCNF) Audit
- **Definition**: A relation is in BCNF if for every non-trivial functional dependency $X \to Y$, the determinant $X$ is a **superkey**.
- **Analysis**:
  - In all decomposed tables, every determinant is either the primary key or a unique alternate key (`roll_no`, `email`, `course_code`, `dept_code`).
  - There are no overlapping composite candidate keys that share dependent non-prime attributes.
- **Conclusion**: The logical schema is certified in **BCNF**.

---

## 3.3 Justified Denormalization & Trigger Synchronizer

### Denormalized Attribute: `course_offering.enrolled_count`
- **Academic Justification**:
  In a production university portal, course registration generates intense concurrent traffic during add/drop periods. If the system calculated seat availability dynamically using `COUNT(*) FROM enrollment WHERE offering_id = ? AND status = 'Enrolled'`, each read would lock the entire enrollment index range or force table scans, introducing catastrophic transaction serialization bottlenecks. By persisting `enrolled_count` on `course_offering`:
  1. Concurrency control is achieved with a simple, high-speed single-row lock: `SELECT capacity, enrolled_count FROM course_offering WHERE offering_id = ? FOR UPDATE`.
  2. Public catalog queries and capacity gauge widgets render in $O(1)$ constant time with zero join overhead.

- **Trigger Consistency Guarantee**:
  Data drift is prevented by three atomic MySQL triggers (`trg_enrollment_after_insert`, `trg_enrollment_after_update`, `trg_enrollment_after_delete`) that fire inside the exact same transaction as the modifying statement.

---

# PHASE 4: PHYSICAL DESIGN (MYSQL 8 DDL, TRIGGERS, ROUTINES & ROLES)

## 4.1 Foreign Key Delete & Update Rule Rationale

Every foreign key constraint in SIMS has been deliberately assigned an `ON DELETE` and `ON UPDATE` action backed by clear relational semantics:

| Foreign Key | Parent Table | Child Table | ON DELETE | ON UPDATE | Viva Engineering Justification |
|---|---|---|---|---|---|
| `dept_id` | `department` | `faculty` | **RESTRICT** | **CASCADE** | Deleting a department that employs faculty is strictly blocked to prevent orphan payroll and departmental records. |
| `hod_faculty_id` | `faculty` | `department` | **SET NULL** | **CASCADE** | If a faculty member serving as HoD resigns or retires, the department remains active with HoD temporarily set to NULL. |
| `dept_id` | `department` | `student` | **RESTRICT** | **CASCADE** | Prevents accidental deletion of academic cohorts; students must be formally transferred before department removal. |
| `student_id` | `student` | `guardian` | **CASCADE** | **CASCADE** | `guardian` is an existence-dependent weak entity; if a student's profile is expunged, their emergency contacts must be expunged. |
| `dept_id` | `department` | `course` | **RESTRICT** | **CASCADE** | A department's approved syllabus catalog cannot be purged while active degree programs reference it. |
| `course_id` | `course` | `course_offering` | **RESTRICT** | **CASCADE** | A course catalog entry cannot be deleted if historical offerings exist for it. |
| `faculty_id` | `faculty` | `course_offering` | **RESTRICT** | **CASCADE** | Academic offering history requires an immutable record of who instructed the section. |
| `student_id` | `student` | `enrollment` | **RESTRICT** | **CASCADE** | Prevents destruction of student academic transcripts; drop status should be used instead of hard deletion. |
| `offering_id` | `course_offering` | `enrollment` | **RESTRICT** | **CASCADE** | A scheduled class offering cannot be dropped if students are registered in it. |
| `enrollment_id` | `enrollment` | `attendance` | **CASCADE** | **CASCADE** | If an enrollment record is explicitly expunged during orientation, its daily attendance markers are wiped cleanly. |
| `offering_id` | `course_offering` | `exam` | **CASCADE** | **CASCADE** | Deleting a cancelled offering cascades to its internal assessment schedule. |
| `exam_id` | `exam` | `result` | **RESTRICT** | **CASCADE** | Prevents wiping published exam grade sheets; exams with submitted marks must remain immutable. |
| `enrollment_id` | `enrollment` | `result` | **CASCADE** | **CASCADE** | Ties evaluation results strictly to the life of the student enrollment junction record. |
| `dept_id` | `department` | `fee_structure` | **CASCADE** | **CASCADE** | Fee schedules are identifying weak entities dependent entirely on the parent department. |
| `student_id` | `student` | `fee_payment` | **RESTRICT** | **CASCADE** | Financial ledger rows cannot be deleted if a student profile is archived; financial history is immutable. |
| `reviewed_by` | `faculty` | `admission_application` | **SET NULL** | **CASCADE** | If a reviewer faculty leaves, historical admission decisions remain documented with reviewer set to NULL. |
| `student_id` | `student` | `app_user` | **CASCADE** | **CASCADE** | User login credentials are tied directly to active institutional matriculation. |
| `faculty_id` | `faculty` | `app_user` | **CASCADE** | **CASCADE** | User login credentials for faculty cascade delete upon employee master record deletion. |

---

## 4.2 Complete MySQL 8 DDL (`db/schema.sql`)

```sql
-- ============================================================================
-- STUDENT INFORMATION MANAGEMENT SYSTEM (SIMS) - CORE RELATIONAL SCHEMA
-- Database Engine: MySQL 8.0+ | Storage Engine: InnoDB | Charset: utf8mb4
-- ============================================================================

DROP DATABASE IF EXISTS sims_db;
CREATE DATABASE sims_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE sims_db;

-- 1. DEPARTMENT
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
ALTER TABLE department
    ADD CONSTRAINT fk_dept_hod FOREIGN KEY (hod_faculty_id)
        REFERENCES faculty(faculty_id) ON DELETE SET NULL ON UPDATE CASCADE;

-- 3. STUDENT
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
    CONSTRAINT chk_student_semester CHECK (current_semester BETWEEN 1 AND 8),
    CONSTRAINT chk_student_age CHECK (dob <= admission_date - INTERVAL 15 YEAR),
    CONSTRAINT fk_student_dept FOREIGN KEY (dept_id)
        REFERENCES department(dept_id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

-- 4. GUARDIAN (Weak Entity to student)
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
CREATE TABLE course (
    course_id INT AUTO_INCREMENT PRIMARY KEY,
    course_code VARCHAR(20) NOT NULL,
    title VARCHAR(100) NOT NULL,
    credits TINYINT NOT NULL,
    dept_id INT NOT NULL,
    semester_no TINYINT NOT NULL,
    CONSTRAINT uk_course_code UNIQUE (course_code),
    CONSTRAINT chk_course_credits CHECK (credits BETWEEN 1 AND 6),
    CONSTRAINT chk_course_semester CHECK (semester_no BETWEEN 1 AND 8),
    CONSTRAINT fk_course_dept FOREIGN KEY (dept_id)
        REFERENCES department(dept_id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

-- 6. COURSE_OFFERING
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

-- 7. ENROLLMENT (Associative Junction Table)
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
```

---

## 4.3 Secondary Indexes & Query Acceleration Justification (`db/indexes.sql`)

```sql
-- ============================================================================
-- SIMS SECONDARY INDEXES WITH EXPLICIT QUERY ACCELERATION JUSTIFICATIONS
-- ============================================================================

-- 1. Accelerates student roster lookups filtered by offering
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

-- 5. Accelerates gradebook lookups for an exam
-- Query: SELECT * FROM result WHERE exam_id = ? ORDER BY marks_obtained DESC
CREATE INDEX idx_result_exam_marks ON result(exam_id, marks_obtained);

-- 6. Accelerates pending application queue filtering on the dashboard
-- Query: SELECT * FROM admission_application WHERE status = 'Pending' ORDER BY applied_on ASC
CREATE INDEX idx_application_status_date ON admission_application(status, applied_on);
```

---

## 4.4 Views Specification (`db/views.sql`)

```sql
-- ============================================================================
-- SIMS SYSTEM VIEWS (LIVE AGGREGATIONS & REPORTING GATES)
-- ============================================================================

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
    d.dept_id,
    d.dept_code,
    d.dept_name,
    COUNT(DISTINCT e.offering_id) AS total_courses_enrolled,
    ROUND(COALESCE(AVG(r.marks_obtained), 0), 2) AS average_marks
FROM student s
JOIN department d ON s.dept_id = d.dept_id
LEFT JOIN enrollment e ON s.student_id = e.student_id AND e.status = 'Enrolled'
LEFT JOIN result r ON e.enrollment_id = r.enrollment_id
GROUP BY s.student_id, d.dept_id;

-- 2. Course Offering Statistics & Capacity Utilization
CREATE OR REPLACE VIEW v_course_offering_stats AS
SELECT
    co.offering_id,
    c.course_code,
    c.title AS course_title,
    c.credits,
    d.dept_code,
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
    d.dept_code,
    s.current_semester,
    fs.amount AS semester_fee_due,
    COALESCE(SUM(fp.amount), 0) AS total_paid,
    (fs.amount - COALESCE(SUM(fp.amount), 0)) AS balance_due,
    CASE
        WHEN COALESCE(SUM(fp.amount), 0) >= fs.amount THEN 'Fully Paid'
        WHEN COALESCE(SUM(fp.amount), 0) > 0 THEN 'Partial'
        ELSE 'Unpaid'
    END AS payment_status,
    CASE
        WHEN (fs.amount - COALESCE(SUM(fp.amount), 0)) > 0 THEN 1
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
```

---

## 4.5 Triggers Specification (`db/triggers.sql`)

```sql
DELIMITER $$

-- 1. Guard against full offering and inactive student registration
CREATE TRIGGER trg_enrollment_before_insert
BEFORE INSERT ON enrollment
FOR EACH ROW
BEGIN
    DECLARE v_capacity SMALLINT;
    DECLARE v_enrolled SMALLINT;
    DECLARE v_student_status VARCHAR(20);

    -- Check student active status
    SELECT status INTO v_student_status
    FROM student WHERE student_id = NEW.student_id;

    IF v_student_status != 'Active' THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Registration rejected: Student profile is not Active.';
    END IF;

    -- Check offering capacity
    SELECT capacity, enrolled_count INTO v_capacity, v_enrolled
    FROM course_offering WHERE offering_id = NEW.offering_id;

    IF v_enrolled >= v_capacity THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Registration rejected: Course offering has reached maximum seating capacity.';
    END IF;
END$$

-- 2. Synchronize enrolled_count on new enrollment
CREATE TRIGGER trg_enrollment_after_insert
AFTER INSERT ON enrollment
FOR EACH ROW
BEGIN
    IF NEW.status = 'Enrolled' THEN
        UPDATE course_offering
        SET enrolled_count = enrolled_count + 1
        WHERE offering_id = NEW.offering_id;
    END IF;
END$$

-- 3. Synchronize enrolled_count on status change (e.g. Enrolled <-> Dropped)
CREATE TRIGGER trg_enrollment_after_update
AFTER UPDATE ON enrollment
FOR EACH ROW
BEGIN
    IF OLD.status = 'Enrolled' AND NEW.status != 'Enrolled' THEN
        UPDATE course_offering
        SET enrolled_count = GREATEST(0, enrolled_count - 1)
        WHERE offering_id = NEW.offering_id;
    ELSEIF OLD.status != 'Enrolled' AND NEW.status = 'Enrolled' THEN
        UPDATE course_offering
        SET enrolled_count = enrolled_count + 1
        WHERE offering_id = NEW.offering_id;
    END IF;
END$$

-- 4. Synchronize enrolled_count on record deletion
CREATE TRIGGER trg_enrollment_after_delete
AFTER DELETE ON enrollment
FOR EACH ROW
BEGIN
    IF OLD.status = 'Enrolled' THEN
        UPDATE course_offering
        SET enrolled_count = GREATEST(0, enrolled_count - 1)
        WHERE offering_id = OLD.offering_id;
    END IF;
END$$

-- 5. Enforce exam maximum marks ceiling on result entry/update
CREATE TRIGGER trg_result_before_insert
BEFORE INSERT ON result
FOR EACH ROW
BEGIN
    DECLARE v_max DECIMAL(5,2);
    SELECT max_marks INTO v_max FROM exam WHERE exam_id = NEW.exam_id;
    IF NEW.marks_obtained > v_max THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Integrity violation: marks_obtained cannot exceed exam max_marks.';
    END IF;
END$$

CREATE TRIGGER trg_result_before_update
BEFORE UPDATE ON result
FOR EACH ROW
BEGIN
    DECLARE v_max DECIMAL(5,2);
    SELECT max_marks INTO v_max FROM exam WHERE exam_id = NEW.exam_id;
    IF NEW.marks_obtained > v_max THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Integrity violation: marks_obtained cannot exceed exam max_marks.';
    END IF;
END$$

-- 6. Reject attendance marking for dropped enrollments
CREATE TRIGGER trg_attendance_before_insert
BEFORE INSERT ON attendance
FOR EACH ROW
BEGIN
    DECLARE v_enr_status VARCHAR(20);
    SELECT status INTO v_enr_status FROM enrollment WHERE enrollment_id = NEW.enrollment_id;
    IF v_enr_status = 'Dropped' THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Attendance invalid: Student has Dropped this course offering.';
    END IF;
END$$

-- 7. Audit log triggers on student updates and deletes
CREATE TRIGGER trg_student_after_update
AFTER UPDATE ON student
FOR EACH ROW
BEGIN
    INSERT INTO audit_log (table_name, action, record_id, old_values, new_values, changed_by)
    VALUES (
        'student',
        'UPDATE',
        NEW.student_id,
        JSON_OBJECT('status', OLD.status, 'current_semester', OLD.current_semester, 'email', OLD.email),
        JSON_OBJECT('status', NEW.status, 'current_semester', NEW.current_semester, 'email', NEW.email),
        CURRENT_USER()
    );
END$$

CREATE TRIGGER trg_student_after_delete
AFTER DELETE ON student
FOR EACH ROW
BEGIN
    INSERT INTO audit_log (table_name, action, record_id, old_values, new_values, changed_by)
    VALUES (
        'student',
        'DELETE',
        OLD.student_id,
        JSON_OBJECT('roll_no', OLD.roll_no, 'name', CONCAT(OLD.first_name, ' ', OLD.last_name)),
        NULL,
        CURRENT_USER()
    );
END$$

-- 8. Audit log trigger on fee payment transactions
CREATE TRIGGER trg_fee_payment_after_insert
AFTER INSERT ON fee_payment
FOR EACH ROW
BEGIN
    INSERT INTO audit_log (table_name, action, record_id, old_values, new_values, changed_by)
    VALUES (
        'fee_payment',
        'INSERT',
        NEW.payment_id,
        NULL,
        JSON_OBJECT('student_id', NEW.student_id, 'semester', NEW.semester_no, 'amount', NEW.amount, 'receipt', NEW.receipt_no),
        CURRENT_USER()
    );
END$$

DELIMITER ;
```

---

## 4.6 Stored Procedures & Functions Specification (`db/procedures.sql`)

```sql
DELIMITER $$

-- 1. sp_enroll_student: Atomic Enrollment with Row-Locking against Concurrency Races
CREATE PROCEDURE sp_enroll_student(
    IN p_student_id INT,
    IN p_offering_id INT,
    OUT p_status_code INT,
    OUT p_message VARCHAR(255)
)
proc_label: BEGIN
    DECLARE v_capacity SMALLINT;
    DECLARE v_enrolled SMALLINT;
    DECLARE v_student_status VARCHAR(20);
    DECLARE v_existing_count INT;

    -- Exit handler for unexpected SQLEXCEPTION
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        SET p_status_code = 500;
        SET p_message = 'Database error: Transaction rolled back.';
    END;

    START TRANSACTION;

    -- Step 1: Validate student eligibility
    SELECT status INTO v_student_status
    FROM student WHERE student_id = p_student_id;

    IF v_student_status IS NULL THEN
        ROLLBACK;
        SET p_status_code = 404;
        SET p_message = 'Student record does not exist.';
        LEAVE proc_label;
    ELSEIF v_student_status != 'Active' THEN
        ROLLBACK;
        SET p_status_code = 400;
        SET p_message = CONCAT('Cannot enroll: Student status is ', v_student_status);
        LEAVE proc_label;
    END IF;

    -- Step 2: Prevent duplicate enrollment
    SELECT COUNT(*) INTO v_existing_count
    FROM enrollment
    WHERE student_id = p_student_id AND offering_id = p_offering_id;

    IF v_existing_count > 0 THEN
        ROLLBACK;
        SET p_status_code = 409;
        SET p_message = 'Student is already enrolled in this course offering.';
        LEAVE proc_label;
    END IF;

    -- Step 3: PESSIMISTIC ROW LOCKING - Prevents race condition
    SELECT capacity, enrolled_count INTO v_capacity, v_enrolled
    FROM course_offering
    WHERE offering_id = p_offering_id
    FOR UPDATE;

    IF v_capacity IS NULL THEN
        ROLLBACK;
        SET p_status_code = 404;
        SET p_message = 'Course offering does not exist.';
        LEAVE proc_label;
    END IF;

    IF v_enrolled >= v_capacity THEN
        ROLLBACK;
        SET p_status_code = 409;
        SET p_message = 'Offering capacity is full. Zero seats remaining.';
        LEAVE proc_label;
    END IF;

    -- Step 4: Perform enrollment insertion (triggers will maintain enrolled_count)
    INSERT INTO enrollment (student_id, offering_id, enroll_date, status)
    VALUES (p_student_id, p_offering_id, CURDATE(), 'Enrolled');

    COMMIT;
    SET p_status_code = 200;
    SET p_message = 'Enrollment successfully confirmed.';
END$$

-- 2. sp_approve_admission: Multi-Table Transactional Matriculation
CREATE PROCEDURE sp_approve_admission(
    IN p_application_id INT,
    IN p_reviewer_faculty_id INT,
    OUT p_new_student_id INT,
    OUT p_generated_roll_no VARCHAR(20),
    OUT p_status_code INT,
    OUT p_message VARCHAR(255)
)
proc_label: BEGIN
    DECLARE v_app_status VARCHAR(20);
    DECLARE v_applicant_name VARCHAR(100);
    DECLARE v_email VARCHAR(100);
    DECLARE v_phone VARCHAR(20);
    DECLARE v_dept_id INT;
    DECLARE v_dept_code VARCHAR(10);
    DECLARE v_year_suffix VARCHAR(2);
    DECLARE v_seq INT;
    DECLARE v_first_name VARCHAR(50);
    DECLARE v_last_name VARCHAR(50);

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        SET p_status_code = 500;
        SET p_message = 'Transaction aborted: Failed to approve admission application.';
    END;

    START TRANSACTION;

    SELECT applicant_name, email, phone, dept_id, status
    INTO v_applicant_name, v_email, v_phone, v_dept_id, v_app_status
    FROM admission_application
    WHERE application_id = p_application_id
    FOR UPDATE;

    IF v_app_status IS NULL THEN
        ROLLBACK;
        SET p_status_code = 404;
        SET p_message = 'Admission application not found.';
        LEAVE proc_label;
    ELSEIF v_app_status != 'Pending' THEN
        ROLLBACK;
        SET p_status_code = 400;
        SET p_message = CONCAT('Application cannot be processed. Current status: ', v_app_status);
        LEAVE proc_label;
    END IF;

    -- Parse name
    SET v_first_name = SUBSTRING_INDEX(v_applicant_name, ' ', 1);
    IF LOCATE(' ', v_applicant_name) > 0 THEN
        SET v_last_name = SUBSTRING(v_applicant_name, LOCATE(' ', v_applicant_name) + 1);
    ELSE
        SET v_last_name = 'Scholar';
    END IF;

    -- Generate unique roll number: YY + DEPT_CODE + 3-digit sequence
    SELECT dept_code INTO v_dept_code FROM department WHERE dept_id = v_dept_id;
    SET v_year_suffix = DATE_FORMAT(CURDATE(), '%y');

    SELECT COUNT(*) + 1 INTO v_seq
    FROM student
    WHERE dept_id = v_dept_id AND YEAR(admission_date) = YEAR(CURDATE());

    SET p_generated_roll_no = CONCAT(v_year_suffix, v_dept_code, LPAD(v_seq, 3, '0'));

    -- 1. Insert Student
    INSERT INTO student (
        roll_no, first_name, last_name, email, phone, dob, gender,
        address, dept_id, admission_date, current_semester, status
    ) VALUES (
        p_generated_roll_no, v_first_name, v_last_name, v_email, v_phone,
        DATE_SUB(CURDATE(), INTERVAL 18 YEAR), 'Other', 'Campus Hostel Block A',
        v_dept_id, CURDATE(), 1, 'Active'
    );
    SET p_new_student_id = LAST_INSERT_ID();

    -- 2. Provision App User (Default hashed password for 'student123')
    INSERT INTO app_user (username, password_hash, role, student_id)
    VALUES (
        LOWER(p_generated_roll_no),
        '$2b$12$K8yXv1WvZz5eB0Vw8gY.3eeV1yqGk6s1iZ/t4Qd4Vl7d2kF5bN2ey',
        'student',
        p_new_student_id
    );

    -- 3. Update Application Status
    UPDATE admission_application
    SET status = 'Approved', reviewed_by = p_reviewer_faculty_id, reviewed_on = NOW()
    WHERE application_id = p_application_id;

    -- 4. Audit Log
    INSERT INTO audit_log (table_name, action, record_id, new_values, changed_by)
    VALUES (
        'admission_application', 'UPDATE', p_application_id,
        JSON_OBJECT('status', 'Approved', 'student_id', p_new_student_id, 'roll_no', p_generated_roll_no),
        CURRENT_USER()
    );

    COMMIT;
    SET p_status_code = 200;
    SET p_message = 'Admission approved, student enrolled, and login provisioned.';
END$$

-- 3. sp_record_payment: Financial Integrity & Overpayment Protection
CREATE PROCEDURE sp_record_payment(
    IN p_student_id INT,
    IN p_semester_no TINYINT,
    IN p_amount DECIMAL(10,2),
    IN p_mode VARCHAR(20),
    IN p_receipt_no VARCHAR(50),
    OUT p_status_code INT,
    OUT p_message VARCHAR(255)
)
proc_label: BEGIN
    DECLARE v_dept_id INT;
    DECLARE v_sem_fee DECIMAL(10,2);
    DECLARE v_already_paid DECIMAL(10,2);
    DECLARE v_max_payable DECIMAL(10,2);

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        SET p_status_code = 500;
        SET p_message = 'Payment recording failed: Database rolled back.';
    END;

    START TRANSACTION;

    -- Lookup student department
    SELECT dept_id INTO v_dept_id FROM student WHERE student_id = p_student_id;
    IF v_dept_id IS NULL THEN
        ROLLBACK;
        SET p_status_code = 404;
        SET p_message = 'Student does not exist.';
        LEAVE proc_label;
    END IF;

    -- Lookup fee structure
    SELECT amount INTO v_sem_fee
    FROM fee_structure
    WHERE dept_id = v_dept_id AND semester_no = p_semester_no;

    IF v_sem_fee IS NULL THEN
        ROLLBACK;
        SET p_status_code = 404;
        SET p_message = 'Fee structure not configured for this semester.';
        LEAVE proc_label;
    END IF;

    -- Calculate current paid balance
    SELECT COALESCE(SUM(amount), 0) INTO v_already_paid
    FROM fee_payment
    WHERE student_id = p_student_id AND semester_no = p_semester_no
    FOR UPDATE;

    SET v_max_payable = v_sem_fee - v_already_paid;

    IF p_amount <= 0 THEN
        ROLLBACK;
        SET p_status_code = 400;
        SET p_message = 'Payment amount must be greater than zero.';
        LEAVE proc_label;
    ELSEIF p_amount > v_max_payable THEN
        ROLLBACK;
        SET p_status_code = 400;
        SET p_message = CONCAT('Overpayment rejected. Maximum remaining fee payable: ', v_max_payable);
        LEAVE proc_label;
    END IF;

    -- Insert payment record
    INSERT INTO fee_payment (student_id, semester_no, amount, paid_on, mode, receipt_no)
    VALUES (p_student_id, p_semester_no, p_amount, CURDATE(), p_mode, p_receipt_no);

    COMMIT;
    SET p_status_code = 200;
    SET p_message = 'Payment successfully recorded.';
END$$

-- 4. Stored Function: fn_grade (Percentage -> Letter Grade)
CREATE FUNCTION fn_grade(p_percentage DECIMAL(5,2))
RETURNS VARCHAR(3)
DETERMINISTIC
BEGIN
    IF p_percentage >= 90.0 THEN RETURN 'A+';
    ELSEIF p_percentage >= 80.0 THEN RETURN 'A';
    ELSEIF p_percentage >= 70.0 THEN RETURN 'B';
    ELSEIF p_percentage >= 60.0 THEN RETURN 'C';
    ELSEIF p_percentage >= 50.0 THEN RETURN 'D';
    ELSEIF p_percentage >= 40.0 THEN RETURN 'E';
    ELSE RETURN 'F';
    END IF;
END$$

-- 5. Stored Function: fn_attendance_pct (Enrollment -> Attendance Percentage)
CREATE FUNCTION fn_attendance_pct(p_enrollment_id INT)
RETURNS DECIMAL(5,2)
READS SQL DATA
BEGIN
    DECLARE v_total INT;
    DECLARE v_attended INT;

    SELECT COUNT(*), SUM(CASE WHEN status IN ('Present', 'Late') THEN 1 ELSE 0 END)
    INTO v_total, v_attended
    FROM attendance
    WHERE enrollment_id = p_enrollment_id;

    IF v_total = 0 OR v_total IS NULL THEN
        RETURN 0.00;
    END IF;

    RETURN ROUND((v_attended / v_total) * 100, 2);
END$$

-- 6. Stored Function: fn_student_cgpa (Student ID -> Cumulative Grade Point Average)
CREATE FUNCTION fn_student_cgpa(p_student_id INT)
RETURNS DECIMAL(4,2)
READS SQL DATA
BEGIN
    DECLARE v_cgpa DECIMAL(4,2);

    SELECT ROUND(AVG(
        CASE
            WHEN (r.marks_obtained / ex.max_marks * 100) >= 90 THEN 10.0
            WHEN (r.marks_obtained / ex.max_marks * 100) >= 80 THEN 9.0
            WHEN (r.marks_obtained / ex.max_marks * 100) >= 70 THEN 8.0
            WHEN (r.marks_obtained / ex.max_marks * 100) >= 60 THEN 7.0
            WHEN (r.marks_obtained / ex.max_marks * 100) >= 50 THEN 6.0
            WHEN (r.marks_obtained / ex.max_marks * 100) >= 40 THEN 5.0
            ELSE 0.0
        END
    ), 2) INTO v_cgpa
    FROM enrollment e
    JOIN result r ON e.enrollment_id = r.enrollment_id
    JOIN exam ex ON r.exam_id = ex.exam_id
    WHERE e.student_id = p_student_id;

    RETURN COALESCE(v_cgpa, 0.00);
END$$

DELIMITER ;
```

---

## 4.7 Database Roles & Security Grants (`db/roles.sql`)

```sql
-- ============================================================================
-- SIMS SECURITY: PRINCIPLE OF LEAST PRIVILEGE DATABASE ROLES
-- ============================================================================

CREATE ROLE IF NOT EXISTS sims_admin;
CREATE ROLE IF NOT EXISTS sims_faculty;
CREATE ROLE IF NOT EXISTS sims_student;

-- Administrator Privileges: Full execution and read/write on domain tables
GRANT SELECT, INSERT, UPDATE, DELETE ON sims_db.* TO sims_admin;
GRANT EXECUTE ON PROCEDURE sims_db.sp_enroll_student TO sims_admin;
GRANT EXECUTE ON PROCEDURE sims_db.sp_approve_admission TO sims_admin;
GRANT EXECUTE ON PROCEDURE sims_db.sp_record_payment TO sims_admin;
GRANT EXECUTE ON FUNCTION sims_db.fn_grade TO sims_admin;
GRANT EXECUTE ON FUNCTION sims_db.fn_attendance_pct TO sims_admin;
GRANT EXECUTE ON FUNCTION sims_db.fn_student_cgpa TO sims_admin;

-- Faculty Privileges: Attendance, Results, View rosters
GRANT SELECT ON sims_db.v_student_overview TO sims_faculty;
GRANT SELECT ON sims_db.v_course_offering_stats TO sims_faculty;
GRANT SELECT ON sims_db.course_offering TO sims_faculty;
GRANT SELECT ON sims_db.enrollment TO sims_faculty;
GRANT SELECT, INSERT, UPDATE ON sims_db.attendance TO sims_faculty;
GRANT SELECT, INSERT, UPDATE ON sims_db.exam TO sims_faculty;
GRANT SELECT, INSERT, UPDATE ON sims_db.result TO sims_faculty;
GRANT EXECUTE ON FUNCTION sims_db.fn_grade TO sims_faculty;
GRANT EXECUTE ON FUNCTION sims_db.fn_attendance_pct TO sims_faculty;

-- Student Privileges: Read-only access to own performance and catalog
GRANT SELECT ON sims_db.v_course_offering_stats TO sims_student;
GRANT SELECT ON sims_db.v_attendance_summary TO sims_student;
GRANT SELECT ON sims_db.v_fee_status TO sims_student;
GRANT EXECUTE ON PROCEDURE sims_db.sp_enroll_student TO sims_student;
GRANT EXECUTE ON FUNCTION sims_db.fn_grade TO sims_student;
GRANT EXECUTE ON FUNCTION sims_db.fn_attendance_pct TO sims_student;
GRANT EXECUTE ON FUNCTION sims_db.fn_student_cgpa TO sims_student;
```

---

# PHASE 5: SHOWCASE QUERY CATALOGUE (25 SHOWCASE QUERIES)

The 25 hand-crafted SQL showcase queries are categorized below with full executable SQL, parameterization strategy, educational objective, and expected result set shape. Each query is designed to demonstrate deep relational database mechanics during the viva examination.

---

### Group A: Joins (6 Queries)

#### Q01. Inner Join: Course Offerings with Instructor & Department
- **Viva Objective**: Demonstrates clean multi-way inner join resolving foreign surrogate keys into human-readable departmental and faculty titles.
- **SQL Query**:
`sql
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
`
- **Expected Result Shape**:
  - offering_id (INT), course_code (VARCHAR), course_title (VARCHAR), credits (TINYINT), dept_code (VARCHAR), dept_name (VARCHAR), instructor_name (VARCHAR), cademic_year (VARCHAR), 	erm (ENUM), capacity (SMALLINT), enrolled_count (SMALLINT).
  - Returns: ~60 rows (All active course offerings).

#### Q02. Left Outer Join: Unassigned Students with Zero Enrollments
- **Viva Objective**: Demonstrates finding orphan or unassigned records using LEFT JOIN ... WHERE right_table.PK IS NULL.
- **SQL Query**:
`sql
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
`
- **Expected Result Shape**:
  - student_id (INT),
oll_no (VARCHAR), student_name (VARCHAR), email (VARCHAR), dept_code (VARCHAR), current_semester (TINYINT), status (ENUM).
  - Returns: Rows representing newly approved students who have matriculated but not yet selected elective courses.

#### Q03. Full Outer Join Equivalent: Departments Without Courses & Courses Without Departments
- **Viva Objective**: MySQL lacks native FULL OUTER JOIN. This demonstrates the ANSI SQL compliant emulation using LEFT JOIN unified with RIGHT JOIN excluding intersections.
- **SQL Query**:
`sql
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
`
- **Expected Result Shape**:
  - dept_code (VARCHAR/NULL), dept_name (VARCHAR/NULL), course_code (VARCHAR/NULL), course_title (VARCHAR/NULL).
  - Returns: Comprehensive matrix revealing courses lacking departmental ownership or new departments with zero approved syllabus courses.

#### Q04. Self-Join: Faculty Members Alongside Their Head of Department (HoD)
- **Viva Objective**: Demonstrates traversing unary recursive relationships by joining a table with itself under aliases (
 for employee, hod for manager).
- **SQL Query**:
`sql
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
`
- **Expected Result Shape**:
  -
aculty_id (INT),
aculty_name (VARCHAR), designation (ENUM), dept_code (VARCHAR), hod_name (VARCHAR), is_department_head (VARCHAR).
  - Returns: 25 rows representing all faculty members paired with their department head.

#### Q05. Deep Multi-Table Join: 5-Table Academic Transcript Traversal
- **Viva Objective**: Demonstrates traversing normalized relational paths: student $	o$ enrollment $	o$ course_offering $	o$ course $	o$
esult $	o$ exam.
- **SQL Query**:
`sql
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
WHERE s.roll_no = '26CSE001'
ORDER BY c.course_code, ex.exam_type;
`
- **Expected Result Shape**:
  -
oll_no (VARCHAR), student_name (VARCHAR), course_code (VARCHAR), course_title (VARCHAR), cademic_year (VARCHAR), 	erm (ENUM), exam_type (ENUM), max_marks (DECIMAL), marks_obtained (DECIMAL), percentage (DECIMAL), letter_grade (VARCHAR).
  - Returns: Granular transcript sheet with computed letter grades via stored function.

#### Q06. Cross Join: Combinatorial Examination Slot Matrix
- **Viva Objective**: Demonstrates Cartesian product generation (CROSS JOIN) to construct an exhaustive schedule allocation matrix without physical database tables.
- **SQL Query**:
`sql
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
`
- **Expected Result Shape**:
  - course_code (VARCHAR), course_title (VARCHAR), day_name (VARCHAR), 	ime_window (VARCHAR), hall_number (VARCHAR).
  - Returns:  	imes 5$ schedule assignment rows for examination room allocations.

---

### Group B: Aggregations & Grouping (5 Queries)

#### Q07. GROUP BY + HAVING: Departmental Cohorts Exceeding Size Threshold
- **Viva Objective**: Clarifies difference between WHERE (pre-aggregation row filtering) and HAVING (post-aggregation group filtering).
- **SQL Query**:
`sql
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
`
- **Expected Result Shape**:
  - dept_code (VARCHAR), dept_name (VARCHAR), 	otal_enrolled_students (BIGINT), ctive_students (BIGINT), vg_current_semester (DECIMAL).
  - Returns: Aggregated rows for major departments passing the minimum student volume threshold.

#### Q08. Statistical Distribution: Comprehensive Marks Summary Per Course Offering
- **Viva Objective**: Demonstrates standard statistical aggregate functions (COUNT, SUM, AVG, MIN, MAX, STDDEV) in a single query.
- **SQL Query**:
`sql
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
`
- **Expected Result Shape**:
  - offering_id (INT), course_code (VARCHAR), course_title (VARCHAR), exam_type (ENUM), max_marks (DECIMAL), evaluations_conducted (BIGINT), verage_score (DECIMAL), lowest_score (DECIMAL), highest_score (DECIMAL), standard_deviation (DECIMAL).

#### Q09. Multi-Tier Financial Aggregation: Tuition Collected by Department & Semester
- **Viva Objective**: Demonstrates multi-column hierarchical grouping and financial roll-up reconciliation across academic terms.
- **SQL Query**:
`sql
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
`
- **Expected Result Shape**:
  - dept_code (VARCHAR), dept_name (VARCHAR), semester_no (TINYINT), 	ransaction_count (BIGINT), students_paid_count (BIGINT), 	otal_tuition_collected (DECIMAL).

#### Q10. Conditional Aggregation: Course Pass Rates (Passing Threshold $\ge 40\%$)
- **Viva Objective**: Illustrates pivoting boolean criteria into ratios using conditional aggregation (SUM(CASE WHEN ... THEN 1 ELSE 0 END) / COUNT(*)).
- **SQL Query**:
`sql
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
`
- **Expected Result Shape**:
  - offering_id (INT), course_code (VARCHAR), course_title (VARCHAR), exam_type (ENUM), 	otal_candidates (BIGINT), passed_candidates (BIGINT),
ailed_candidates (BIGINT), pass_percentage (DECIMAL).

#### Q11. Institutional Attendance Distribution: University Attendance Quality Ratio
- **Viva Objective**: Groups university attendance records to report global institutional engagement benchmarks for accreditation audits.
- **SQL Query**:
`sql
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
`
- **Expected Result Shape**:
  - dept_code (VARCHAR), 	otal_recorded_sessions (BIGINT), present_count (BIGINT), late_count (BIGINT), bsent_count (BIGINT), ttendance_rate (DECIMAL).

---

### Group C: Subqueries (5 Queries)

#### Q12. Scalar Subquery in SELECT: Individual Score vs Exam Global Average
- **Viva Objective**: Demonstrates evaluating an independent scalar subquery within the projection clause to compute deviations without joining aggregate tables.
- **SQL Query**:
`sql
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
LIMIT 20;
`
- **Expected Result Shape**:
  -
oll_no (VARCHAR), student_name (VARCHAR), course_code (VARCHAR), marks_obtained (DECIMAL), exam_global_average (DECIMAL), deviation_from_average (DECIMAL).

#### Q13. IN / EXISTS Predicate: Active Students with Outstanding Arrears
- **Viva Objective**: Explains optimizer semi-join strategies and demonstrates why WHERE EXISTS (...) is safer and faster than IN when subqueries might contain NULLs.
- **SQL Query**:
`sql
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
`
- **Expected Result Shape**:
  - student_id (INT),
oll_no (VARCHAR), student_name (VARCHAR), dept_code (VARCHAR), current_semester (TINYINT).

#### Q14. Correlated Subquery: Students with CGPA Exceeding Departmental Benchmark
- **Viva Objective**: Essential viva concept: Subquery references the outer query tuple (s.dept_id) on each iteration to compute dynamic departmental cutoff thresholds.
- **SQL Query**:
`sql
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
`
- **Expected Result Shape**:
  -
oll_no (VARCHAR), student_name (VARCHAR), dept_code (VARCHAR), student_cgpa (DECIMAL), dept_average_cgpa (DECIMAL).

#### Q15. Derived Table in FROM: Departmental Aggregation Over Student Averages
- **Viva Objective**: Illustrates materializing an inline view in the FROM clause to execute second-level statistical aggregations over pre-aggregated student scores.
- **SQL Query**:
`sql
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
`
- **Expected Result Shape**:
  - dept_code (VARCHAR), dept_name (VARCHAR), evaluated_students_count (BIGINT), dept_overall_mean (DECIMAL), dept_top_mean (DECIMAL).

#### Q16. Quantified Comparison (ALL/ANY): High-Scoring Benchmark Students
- **Viva Objective**: Demonstrates relational comparison operators > ALL (SELECT ...) to isolate entries exceeding every individual value returned by a subquery.
- **SQL Query**:
`sql
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
`
- **Expected Result Shape**:
  -
oll_no (VARCHAR), student_name (VARCHAR), course_code (VARCHAR), marks_obtained (DECIMAL).

---

### Group D: Window Functions & Common Table Expressions (5 Queries)

#### Q17. DENSE_RANK Partitioning: Top 3 Scholars Per Academic Department
- **Viva Objective**: Demonstrates analytic window ranking with PARTITION BY and explains why DENSE_RANK() avoids ranking gaps compared to RANK().
- **SQL Query**:
`sql
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
`
- **Expected Result Shape**:
  - dept_code (VARCHAR),
ank_within_dept (BIGINT),
oll_no (VARCHAR), student_name (VARCHAR), cgpa (DECIMAL).

#### Q18. Cumulative Window Aggregation: Running Total of University Tuition Receipts
- **Viva Objective**: Demonstrates cumulative calculations using unbounded preceding framing: SUM(...) OVER (ORDER BY ... ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW).
- **SQL Query**:
`sql
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
`
- **Expected Result Shape**:
  - calendar_month (VARCHAR), monthly_collection (DECIMAL), cumulative_revenue_to_date (DECIMAL).

#### Q19. Analytic Offset LAG: Semester-Over-Semester Student Performance Delta
- **Viva Objective**: Demonstrates comparing successive rows within partitions without self-joins using the LAG(value, offset) window function.
- **SQL Query**:
`sql
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
`
- **Expected Result Shape**:
  - student_id (INT),
oll_no (VARCHAR), student_name (VARCHAR), semester_no (TINYINT), semester_average (DECIMAL), prior_sem_average (DECIMAL), performance_delta (DECIMAL).

#### Q20. Recursive CTE: Generating 8-Semester Curriculum Progression Matrix
- **Viva Objective**: Explains recursive CTE anchor member and recursive member termination mechanics in MySQL 8 to generate sequential data without tables.
- **SQL Query**:
`sql
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
`
- **Expected Result Shape**:
  - semester_number (INT), semester_title (VARCHAR), 	otal_courses_designed (BIGINT), 	otal_credits_prescribed (DECIMAL).

#### Q21. Multi-Stage CTE: Fee Defaulter Audit with Dynamic Late Fines
- **Viva Objective**: Demonstrates modular query composition using chained CTEs to break down intricate financial auditing into readable, maintainable logical steps.
- **SQL Query**:
`sql
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
`
- **Expected Result Shape**:
  - student_id (INT),
oll_no (VARCHAR), student_name (VARCHAR), dept_code (VARCHAR), current_semester (TINYINT), 	uition_due (DECIMAL), 	otal_paid (DECIMAL), alance_remaining (DECIMAL), penalty_fine (DECIMAL), 	otal_outstanding (DECIMAL).

---

### Group E: Set Operations (2 Queries)

#### Q22. UNION vs UNION ALL: Unified Campus Personnel Directory
- **Viva Objective**: Demonstrates combining disparate entity structures with compatible column projections, contrasting UNION (costly sort deduplication) with UNION ALL (instant append).
- **SQL Query**:
`sql
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
`
- **Expected Result Shape**:
  - identity_type (VARCHAR), unique_code (VARCHAR),
ull_name (VARCHAR), email (VARCHAR), dept_code (VARCHAR).
  - Returns: ~325 combined university personnel records.

#### Q23. Set Difference (EXCEPT): Curriculum Offerings Offered in 2025 but Dropped in 2026
- **Viva Objective**: Proves understanding of relational set difference using the modern MySQL 8.0.31+ EXCEPT operator to audit curriculum retention.
- **SQL Query**:
`sql
SELECT c.course_code, c.title AS course_title
FROM course c
JOIN course_offering co ON c.course_id = co.course_id
WHERE co.academic_year = '2024-2025'
EXCEPT
SELECT c.course_code, c.title AS course_title
FROM course c
JOIN course_offering co ON c.course_id = co.course_id
WHERE co.academic_year = '2025-2026';
`
- **Expected Result Shape**:
  - course_code (VARCHAR), course_title (VARCHAR).
  - Returns: Catalog courses offered during academic year 2024-2025 that received zero scheduled offerings in 2025-2026.

---

### Group F: Data Modification DML Demonstrations (2 Queries)

#### Q24. INSERT ... SELECT with Transaction Demo & Forced ROLLBACK: Cohort Promotion
- **Viva Objective**: Proves transactional DML atomicity. Migrates eligible semester-1 students into semester-2 and copies audit snapshots, followed by an explicit ROLLBACK to preserve pristine test data.
- **SQL Query**:
`sql
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
`
- **Expected Result Shape**:
  - 	otal_students_promoted (BIGINT).
  - Post-execution verification proves udit_log and student tables remain completely unmodified after ROLLBACK.

#### Q25. Multi-Table UPDATE with JOIN: Batch Academic Scholarship Fee Discount
- **Viva Objective**: Demonstrates enterprise multi-table UPDATE ... JOIN syntax, updating tuition schedules joined with departmental criteria within an atomic rollback block.
- **SQL Query**:
`sql
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
`
- **Expected Result Shape**:
  - dept_code (VARCHAR), semester_no (TINYINT), discounted_tuition_fee (DECIMAL).
  - Post-execution verification proves base fee reverts to original figure.


---

# PHASE 6: APPLICATION & UI DESIGN (JOBGIO SPECIFICATION & WIREFRAMES)

## 6.1 Architecture Overview
The application follows a clean 3-tier decoupled architecture:
1. **Presentation Layer**: Jinja2 templates styled with custom CSS tokens mirroring the Jobgio design language. Vanilla JavaScript handles AJAX interactions and updates Chart.js instances.
2. **Repository Layer**: Thin Flask blueprints invoke pure, hand-written parameterized SQL repository classes. Connection pooling is managed using `mysql.connector.pooling`.
3. **Database Engine**: MySQL 8.0+ enforces business rules through constraints, triggers, and stored procedures.

```
+-----------------------------------------------------------------------------------------+
|                                    SIMS 3-TIER ARCHITECTURE                             |
+-----------------------------------------------------------------------------------------+
    [ Client Browser ]
           |  (HTTP / JSON AJAX)
           v
    [ Flask Application Controller ]
           |
           +---> [ Authentication & RBAC Gate ]
           |
           +---> [ Repositories (Pure SQL, Zero ORM) ]
                     |  (Parameterized Queries %s)
                     v
           [ MySQL 8 Connection Pool ]
                     |
                     v
           +-------------------------------------------------------------+
           |                      SIMS_DB (MySQL 8)                      |
           |  - 15 Normalized Tables (InnoDB, PK/FK/CHECK/UNIQUE)         |
           |  - 6 Triggers (Integrity, Capacity, Auditing)               |
           |  - 3 Stored Procedures (Pessimistic Locking, Matriculation) |
           |  - 3 Stored Functions (Grading, Attendance, CGPA)           |
           |  - 6 System Views & 6 Performance Indexes                   |
           +-------------------------------------------------------------+
```

---

## 6.2 Jobgio Visual Language & Design Tokens
The user interface faithfully replicates the provided Jobgio dashboard screenshot:
- **Outer Backdrop**: Smooth ambient gray gradient (`linear-gradient(135deg, #CFCFCF 0%, #B9B9B9 100%)`).
- **App Shell**: Floating container (`#F2F2F2`) with `36px` border-radius and deep diffuse drop shadow (`0 30px 80px rgba(0,0,0,0.18)`), positioned with a `36px` viewport margin.
- **Sidebar**: Pure white (`#FFFFFF`) with `32px` inner border-radius. Active menu item is an ink-black pill (`#0E0E0E`) with white text and icon; inactive items feature muted typography (`#8E8E8E`) with circular light-gray icon tiles.
- **Card Styling**: Ultra-soft subtle gradient (`#FFFFFF` to `#F5F5F5`), `28px` border-radius, `1px solid rgba(255,255,255,0.8)` rim, and soft ambient elevation.
- **Typography & Monochrome Palette**: Plus Jakarta Sans / Manrope, tabular figures for statistics, deep ink black (`#0E0E0E`), muted slate (`#8E8E8E`), light gray pill accents (`#E6E6E6`).
- **Micro-Status Indicators**: Discrete colored dots maintain monochrome elegance without visual noise: Green (`#3DDC84`, Active), Orange (`#F59E42`, Pending/Suspended), Red (`#FF4D4F`, Dropped/Defaulter), Gray (`#8E8E8E`, Graduated).
- **"Show SQL" Pill**: Located on every page to instantly reveal the exact SQL query and parameters used to render the view.

---

## 6.3 ASCII UI Wireframes

### 6.3.1 Floating Shell & Persistent Navigation Shell
`
+------------------------------------------------------------------------------------------------------------------------+
|  [SIMS] University Portal                        [ Search student, course, faculty... (Ctrl+K) ]      (Bell: 3) (Profile) |
|  +-------------------+ +---------------------------------------------------------------------------------------------+  |
|  | (•) Dashboard     | | Page Header: Breadcrumb / Active Module Title                      [ Show SQL Pill (1 Query) ] |  |
|  | ( ) Students      | |                                                                                               |  |
|  | ( ) Faculty       | |                                                                                               |  |
|  | ( ) Departments   | |                                                                                               |  |
|  | ( ) Courses       | |                     [ PRIMARY PAGE VIEW CONTENT CONTAINER ]                                   |  |
|  | ( ) Enrollments   | |                                                                                               |  |
|  | ( ) Attendance    | |                                                                                               |  |
|  | ( ) Results       | |                                                                                               |  |
|  | ( ) Fees          | |                                                                                               |  |
|  | ( ) Reports       | |                                                                                               |  |
|  | ( ) DB Insights   | |                                                                                               |  |
|  | ( ) Settings      | |                                                                                               |  |
|  |                   | |                                                                                               |  |
|  | ----------------- | |                                                                                               |  |
|  | [Avatar] Dr. Verma| |                                                                                               |  |
|  | Admin (sims_admin)| |                                                                                               |  |
|  | [Logout Button]   | |                                                                                               |  |
|  +-------------------+ +---------------------------------------------------------------------------------------------+  |
+------------------------------------------------------------------------------------------------------------------------+
`

---

### 6.3.2 Centered Light Glass Login Screen
`
+------------------------------------------------------------------------------------------------------------------------+
|                                    PAGE BACKDROP (Soft Gray Gradient #CFCFCF -> #B9B9B9)                               |
|                                                                                                                        |
|                                         +-----------------------------------------+                                    |
|                                         |           [SIMS UNIVERSITY PORTAL]      |                                    |
|                                         |            Database-First SIMS Core     |                                    |
|                                         |                                         |                                    |
|                                         |   Username or Roll Number               |                                    |
|                                         |   [ admin / faculty / 26CSE001       ]  |                                    |
|                                         |                                         |                                    |
|                                         |   Password                              |                                    |
|                                         |   [ ••••••••••••••••••••••••••••••   ]  |                                    |
|                                         |                                         |                                    |
|                                         |   Role Target                           |                                    |
|                                         |   (•) Admin    ( ) Faculty   ( ) Student|                                    |
|                                         |                                         |                                    |
|                                         |   [        SIGN IN TO PORTAL        ]   |                                    |
|                                         |                                         |                                    |
|                                         |   Demo Access:                          |                                    |
|                                         |   • admin / admin123 (DB Admin)         |                                    |
|                                         |   • faculty / faculty123 (Instructor)   |                                    |
|                                         |   • student / student123 (Scholar)      |                                    |
|                                         +-----------------------------------------+                                    |
+------------------------------------------------------------------------------------------------------------------------+
`

---

### 6.3.3 Dashboard (Faithful to Jobgio Layout)
`
+------------------------------------------------------------------------------------------------------------------------+
|  [SIMS]                                        [ Global Search... (Ctrl+K) ]                     (Bell) (Profile)      |
|                                                                                                                        |
|  (•) Dashboard      +-----------------------------------------------------------------------------------------------+  |
|  ( ) Students       | Quick Stats   Live counts from database                              [ Show SQL Pill (6 Queries) ]   |
|  ( ) Faculty        | +-----------+ +-----------+ +-----------+ +-----------+ +-----------+ +-----------+          |  |
|  ( ) Departments    | |   (User)  | |  (Bldg)   | |  [Black]  | |   (Doc)   | |  (Alert)  | |  (Report) |          |  |
|  ( ) Courses        | |    324    | |     6     | |    42     | |    28     | |   1,540   | |    18     |          |  |
|  ( ) Enrollments    | |   Total   | |   Total   | |  Active   | |  Faculty  | |   Total   | |  Pending  |          |  |
|  ( ) Attendance     | |  Students | |   Depts   | |  Courses  | |  Members  | |Enrollments| |Admissions |          |  |
|  ( ) Results        | |           | |           | |    (->)   | |           | |           | |           |          |  |
|  ( ) Fees           | +-----------+ +-----------+ +-----------+ +-----------+ +-----------+ +-----------+          |  |
|  ( ) Reports        +-----------------------------------------------------------------------------------------------+  |
|  ( ) DB Insights                                                                                                       |
|  ( ) Settings       +-------------------------------------------------+ +-------------------------------------------+  |
|                     | Statistics        (● Admissions  ○ Enrollments) | | Pending Approvals                     (O) |  |
|                     |                               [ Year: 2026 v ]  | |                                           |  |
|                     |  8K |                                           | | (A) Aarav Sharma                          |  |
|                     |  6K |          |        [6.4K]    |             | |     CSE · Jun 10, 2026          [Pending] |  |
|                     |  4K |    |     |  |     |  |   |  |     |       | | (P) Priya Nair                            |  |
|                     |  2K | |  |  |  |  |  |  |  |   |  |  |  |  |    | |     ECE · Jun 12, 2026          [Pending] |  |
|                     |   0 +-+--+--+--+--+--+--+--+---+--+--+--+--+--  | | (R) Rahul Varma                           |  |
|                     |      Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov| |     MECH · Jun 14, 2026         [Pending] |  |
|  [George]           +-------------------------------------------------+ +-------------------------------------------+  |
|  Admin              +-----------------------------------------------------------------------------------------------+  |
|  (Logout)           | Manage Students                                        [ Status: All v ]      [ Export CSV ^ ]|  |
|                     | [ ] Student               Department    Semester    Status       Admission Date     Actions   |  |
|                     | [ ] Aarav Sharma 26CSE001 Computer Sci    Sem 4     ● Active     Jun 10, 2026       [ ... ]   |  |
|                     | [ ] Priya Nair   26ECE014 Electronics     Sem 2     ● Active     Jun 08, 2026       [ ... ]   |  |
|                     | [ ] Rohan Sen    25ME032  Mechanical      Sem 6     ● Suspended  Feb 02, 2025       [ ... ]   |  |
|                     +-----------------------------------------------------------------------------------------------+  |
+------------------------------------------------------------------------------------------------------------------------+
`

---

### 6.3.4 Students Directory & Add/Edit Slide-Over Drawer
`
+------------------------------------------------------------------------------------------------------------------------+
|  Manage Students (324 Total)       [ Filter Dept: All v ]  [ Sem: All v ]  [ + Add Student ]   [ Show SQL: v_student ] |
|  +---------------------------------------------------------------------------------------+ +-------------------------+ |
|  | [ ] Roll No   Name         Department   Semester  Status     CGPA   Actions           | | ADD / EDIT STUDENT DRAWER | |
|  |---------------------------------------------------------------------------------------| | First Name:             | |
|  | [ ] 26CSE001  Aarav Sharma Computer Sci Sem 4     ● Active   8.94   [View] [Edit] [Del]| | [ Aarav               ] | |
|  | [ ] 26CSE002  Diya Patel   Computer Sci Sem 4     ● Active   9.20   [View] [Edit] [Del]| | Last Name:              | |
|  | [ ] 26ECE014  Priya Nair   Electronics  Sem 2     ● Active   7.85   [View] [Edit] [Del]| | [ Sharma              ] | |
|  | [ ] 25ME032   Rohan Sen    Mechanical   Sem 6     ● Suspended 6.40  [View] [Edit] [Del]| | Email (Unique):         | |
|  | [ ] 24CE009   Kavita Roy   Civil        Sem 8     ● Graduated 8.12  [View] [Edit] [Del]| | [ aarav@sims.edu      ] | |
|  |                                                                                       | | Date of Birth (>=15yr): | |
|  | Showing 1 - 25 of 324 records                [ << Prev ]  [ 1 ]  [ 2 ] ... [ Next >> ]| | [ 2005-04-12          ] | |
|  +---------------------------------------------------------------------------------------+ | Department:             | |
|                                                                                            | [ Computer Science (1)  ] | |
|                                                                                            | [ SAVE STUDENT VIA DML  ] | |
|                                                                                            +-------------------------+ |
+------------------------------------------------------------------------------------------------------------------------+
`

---

### 6.3.5 Comprehensive Student Dossier & Profile Inspector (/students/<id>)
`
+------------------------------------------------------------------------------------------------------------------------+
|  < Back to Students Directory                                                         [ Show SQL: 5 Repository Calls ] |
|  +----------------------------------------------------+ +------------------------------------------------------------+  |
|  | [Avatar Photo]  Aarav Sharma                       | | ACADEMIC PERFORMANCE SUMMARY                               |  |
|  | Roll No: 26CSE001 | Dept: Computer Science & Eng.  | | Cumulative GPA (fn_student_cgpa):    [  8.94 / 10.0  ]     |  |
|  | Status: ● Active   | Current Semester: 4            | | Overall Attendance (fn_attendance):   [    88.5%     ]     |  |
|  | Email: aarav@sims.edu | Phone: +91 98765 43210     | | Fee Clearance Status (v_fee_status): [ Fully Cleared ]     |  |
|  +----------------------------------------------------+ +------------------------------------------------------------+  |
|  +-------------------------------------------------------------------------------------------------------------------+  |
|  | EMERGENCY CONTACTS & GUARDIANS (Existence-Dependent Weak Entity - ON DELETE CASCADE)                             |  |
|  | • Suresh Sharma (Father) - +91 98765 43211 | Address: Flat 402, Green Park Avenue, New Delhi                      |  |
|  | • Meena Sharma (Mother)  - +91 98765 43212 | Relation: Primary Guardian                                           |  |
|  +-------------------------------------------------------------------------------------------------------------------+  |
|  +----------------------------------------------------+ +------------------------------------------------------------+  |
|  | ENROLLED OFFERINGS & EVALUATIONS                   | | AUDIT LEDGER TRAIL (From audit_log Trigger)                |  |
|  | • CS201 Data Structures (Sem 4, Fall 2026)         | | • 2026-06-10 10:14 - INSERT student (System Admin)         |  |
|  |   - Internal: 28/30 | Midterm: 44/50 | Final: 88/100| | • 2026-08-01 09:30 - UPDATE semester 3 -> 4 (Promote Job)  |  |
|  |   - Letter Grade: A  (fn_grade: 86.6%)             | | • 2026-09-15 14:22 - INSERT fee_payment (UPI Receipt #940) |  |
|  +----------------------------------------------------+ +------------------------------------------------------------+  |
+------------------------------------------------------------------------------------------------------------------------+
`

---

### 6.3.6 Course Offerings & Seat Capacity Gauges (/offerings)
`
+------------------------------------------------------------------------------------------------------------------------+
|  Course Offerings & Capacity (Fall 2026)                [ + Open Offering ]           [ Show SQL: v_offering_stats ]   |
|  +-------------------------------------------------------------------------------------------------------------------+  |
|  | Code   Title                Instructor        Credits  Capacity  Enrolled  Utilization Gauge             Status   |  |
|  |-------------------------------------------------------------------------------------------------------------------|  |
|  | CS201  Data Structures      Prof. Alan Turing    4        60        58     [=======================..] 96.6% ALMOST |  |
|  | CS202  Database Systems     Prof. Edgar Codd     4        60        60     [=========================] 100%  FULL   |  |
|  | CS203  Computer Networks    Prof. Cerf & Kahn    3        50        32     [================.........] 64.0% AVAIL  |  |
|  | EC201  Digital Circuits     Prof. Claude Shannon 4        45        45     [=========================] 100%  FULL   |  |
|  +-------------------------------------------------------------------------------------------------------------------+  |
|  | * Trigger trg_enrollment_before_insert blocks registration when Enrolled == Capacity with SQLSTATE 45000.         |  |
+------------------------------------------------------------------------------------------------------------------------+
`

---

### 6.3.7 Attendance Roll-Call Sheet (/attendance)
`
+------------------------------------------------------------------------------------------------------------------------+
|  Daily Class Attendance Marker                                                 [ Show SQL: Atomic Batch INSERT ]       |
|  Offering: [ CS202 - Database Systems v ]   Date: [ 2026-10-20 ]   Instructor: Prof. Edgar Codd                        |
|  +-------------------------------------------------------------------------------------------------------------------+  |
|  | Roll No    Student Name            Current Attendance %   Attendance Status                                       |  |
|  |-------------------------------------------------------------------------------------------------------------------|  |
|  | 26CSE001   Aarav Sharma                    92.0%          (•) Present   ( ) Late   ( ) Absent                     |  |
|  | 26CSE002   Diya Patel                      96.5%          (•) Present   ( ) Late   ( ) Absent                     |  |
|  | 26CSE003   Karan Mehta                     68.0%          ( ) Present   ( ) Late   (•) Absent                     |  |
|  | 26CSE004   Sneha Verma                     85.0%          ( ) Present   (•) Late   ( ) Absent                     |  |
|  +-------------------------------------------------------------------------------------------------------------------+  |
|  | [ SUBMIT CLASS ATTENDANCE SHEET (One Atomic Transaction) ]    * Dropped students blocked by trigger.              |  |
+------------------------------------------------------------------------------------------------------------------------+
`

---

### 6.3.8 Examination Results & Gradebook (/results)
`
+------------------------------------------------------------------------------------------------------------------------+
|  Gradebook & Evaluation Ledger                                                  [ Show SQL: Result Trigger Verified ]  |
|  Offering: [ CS202 - Database Systems v ]   Assessment: [ Midterm Exam (Max: 50.0) v ]   Exam Date: 2026-09-18         |
|  +-------------------------------------------------------------------------------------------------------------------+  |
|  | Roll No    Student Name           Marks Obtained (0 - 50)   Percentage   Calculated Grade   Rank (DENSE_RANK)     |  |
|  |-------------------------------------------------------------------------------------------------------------------|  |
|  | 26CSE002   Diya Patel             [ 48.5 ] / 50.0            97.0%            A+                 1                |  |
|  | 26CSE001   Aarav Sharma           [ 45.0 ] / 50.0            90.0%            A+                 2                |  |
|  | 26CSE004   Sneha Verma            [ 41.0 ] / 50.0            82.0%            A                  3                |  |
|  | 26CSE003   Karan Mehta            [ 28.5 ] / 50.0            57.0%            D                  4                |  |
|  +-------------------------------------------------------------------------------------------------------------------+  |
|  | [ SAVE EVALUATION MARKS ]    * Entering 52.0 immediately rejected by trg_result_before_insert.                     |  |
+------------------------------------------------------------------------------------------------------------------------+
`

---

### 6.3.9 Fee Ledger & Defaulter Audit (/fees)
`
+------------------------------------------------------------------------------------------------------------------------+
|  Fee Collections & Defaulters Ledger                                                   [ Show SQL: v_fee_status ]      |
|  [ Filter: All Students v ]  [ Defaulters Only: (X) ]                        [ + Record Fee Payment (sp_record_payment)]|
|  +-------------------------------------------------------------------------------------------------------------------+  |
|  | Roll No    Student Name     Dept   Semester   Fee Due    Amount Paid   Balance Due   Status      Defaulter Flag   |  |
|  |-------------------------------------------------------------------------------------------------------------------|  |
|  | 26CSE003   Karan Mehta      CSE     Sem 4     50,000.00   20,000.00     30,000.00    Partial     ● Defaulter      |  |
|  | 26ECE014   Priya Nair       ECE     Sem 2     45,000.00        0.00     45,000.00    Unpaid      ● Defaulter      |  |
|  | 26CSE001   Aarav Sharma     CSE     Sem 4     50,000.00   50,000.00          0.00    Fully Paid  ○ Cleared        |  |
|  | 26CSE002   Diya Patel       CSE     Sem 4     50,000.00   50,000.00          0.00    Fully Paid  ○ Cleared        |  |
|  +-------------------------------------------------------------------------------------------------------------------+  |
|  | RECORD PAYMENT MODAL: Calls sp_record_payment with overpayment barrier (e.g. paying 35,000 on 30,000 due rejected)|  |
+------------------------------------------------------------------------------------------------------------------------+
`

---

### 6.3.10 DB Insights & Viva Defense Lab (/insights)
`
+------------------------------------------------------------------------------------------------------------------------+
|  DB Insights & Viva Defense Demonstration Lab                                                [ Engine: MySQL 8.0.33 ]   |
|  [ [Tab 1: ER Diagram] | [Tab 2: Schema Browser] | [Tab 3: Query Lab] | [Tab 4: Rollback Demo] | [Tab 5: Audit Log] ]  |
|  +-------------------------------------------------------------------------------------------------------------------+  |
|  | Select Viva Showcase Query: [ Q14: Correlated Subquery - Students Exceeding Dept Average CGPA v ]                |  |
|  | Query Description: Compares each student's CGPA against dynamically evaluated department benchmark.               |  |
|  | SQL Code Window (Read-Only):                                                                                      |  |
|  |   SELECT s.roll_no, CONCAT(s.first_name, ' ', s.last_name), fn_student_cgpa(s.student_id)                        |  |
|  |   FROM student s WHERE fn_student_cgpa(s.student_id) > (SELECT AVG(...) FROM student s2 WHERE s2.dept_id = s.dept_id)|  |
|  |                                                                                                                   |  |
|  |   [ > EXECUTE SHOWCASE QUERY ]               [ SHOW EXPLAIN EXECUTION PLAN ]                                       |  |
|  |-------------------------------------------------------------------------------------------------------------------|  |
|  | EXPLAIN OUTPUT:                                                                                                   |  |
|  | id | select_type        | table | partitions | type | possible_keys          | key                    | rows | Filter|  |
|  | 1  | PRIMARY            | s     | NULL       | ref  | idx_student_dept_status| idx_student_dept_status | 50   | 100.0 |  |
|  | 2  | DEPENDENT SUBQUERY | s2    | NULL       | ref  | idx_student_dept_status| idx_student_dept_status | 50   | 100.0 |  |
|  +-------------------------------------------------------------------------------------------------------------------+  |
|  | TRANSACTION ROLLBACK DEMO BUTTON:                                                                                  |  |
|  | [ Click: Run Concurrency Collision / Capacity Breach Test ] -> Demonstrates atomic ROLLBACK live in front of viva. |  |
+------------------------------------------------------------------------------------------------------------------------+
`


---

## 6.4 REST Routes & SQL Object Mapping

| HTTP Verb | Route | Description | SQL Object / Query Invoked |
|---|---|---|---|
| `GET` | `/` | System Login Screen | `SELECT * FROM app_user WHERE username = ?` |
| `POST` | `/api/auth/login` | Authenticate user | `app_user` lookup + bcrypt password verification |
| `GET` | `/dashboard` | Render Main Dashboard | Multiple views & statistics aggregates |
| `GET` | `/api/dashboard/stats` | Live KPI Counts | `COUNT(*)` queries on student, dept, course, faculty, etc. |
| `GET` | `/api/dashboard/chart` | Monthly Admissions vs Enrollments | `v_monthly_admissions_enrollments` |
| `GET` | `/api/admissions/pending` | List pending applications | `v_pending_approvals` |
| `POST` | `/api/admissions/approve` | Approve admission application | `CALL sp_approve_admission(?, ?, @id, @roll, @code, @msg)` |
| `GET` | `/students` | Manage Students Page | `v_student_overview` with pagination & sorting |
| `POST` | `/api/students/create` | Add new student record | Direct parameterized `INSERT INTO student` |
| `GET` | `/students/<id>` | Student Profile Inspector | Joins on `guardian`, `enrollment`, `result`, `fn_student_cgpa` |
| `GET` | `/offerings` | Course Offerings Directory | `v_course_offering_stats` |
| `POST` | `/api/enrollments/enroll` | Register for course offering | `CALL sp_enroll_student(?, ?, @code, @msg)` |
| `POST` | `/api/attendance/mark` | Record daily attendance sheet | Atomic batch `INSERT INTO attendance` |
| `POST` | `/api/results/save` | Enter exam marks | `INSERT INTO result` (checked by `trg_result_before_insert`) |
| `POST` | `/api/fees/pay` | Record fee installment | `CALL sp_record_payment(?, ?, ?, ?, ?, @code, @msg)` |
| `GET` | `/api/fees/defaulters` | List students with fee arrears | `v_fee_status WHERE is_defaulter = 1` |
| `GET` | `/insights/query-lab` | Run Showcase Viva Query | Executes queries Q01-Q25 with `EXPLAIN` plan generation |
| `POST` | `/insights/transaction-demo` | Run Concurrency/Rollback Test | Triggers intentional violation within transaction |
| `GET` | `/insights/audit-log` | Inspect audit ledger | `SELECT * FROM audit_log ORDER BY changed_at DESC` |

---

# PHASE 7: IMPLEMENTATION PLAN & TESTING STRATEGY

## 7.1 File-by-File Directory Tree
```
sims/
├── app.py                      # Flask Application entry point & blueprint registration
├── config.py                   # Environment configuration & DB connection parameters
├── .env.example                # Template database credentials (host, user, pass, db)
├── requirements.txt            # Python dependencies (Flask, mysql-connector-python, pytest, faker)
├── docker-compose.yml          # Optional MySQL 8.0 + Flask container configuration
├── db/
│   ├── schema.sql              # 15 normalized tables with DDL constraints
│   ├── triggers.sql            # 6 business logic & audit triggers
│   ├── procedures.sql          # 3 stored procedures & 3 stored functions
│   ├── views.sql               # 6 system views for reporting & dashboard
│   ├── indexes.sql             # 6 performance indexes with justifications
│   ├── roles.sql               # Least privilege database roles & GRANT statements
│   ├── seed.py                 # Deterministic seed generator (Faker seed 42)
│   └── queries/
│       ├── joins.sql           # Queries Q01 - Q06
│       ├── aggregates.sql      # Queries Q07 - Q11
│       ├── subqueries.sql      # Queries Q12 - Q16
│       ├── windows_ctes.sql    # Queries Q17 - Q21
│       ├── sets.sql            # Queries Q22 - Q23
│       └── dml.sql             # Queries Q24 - Q25 (with rollback demo)
├── repositories/               # Pure Parameterized SQL Data Repositories
│   ├── db_pool.py              # MySQL Connection Pool Manager
│   ├── students_repo.py        # Student records & profile queries
│   ├── faculty_repo.py         # Faculty rosters & HoD queries
│   ├── courses_repo.py         # Catalog courses & offerings
│   ├── enrollments_repo.py     # Invocation of sp_enroll_student
│   ├── attendance_repo.py      # Attendance sheet transactions
│   ├── results_repo.py         # Result submissions & grading
│   ├── fees_repo.py            # Invocation of sp_record_payment & defaulters
│   ├── admissions_repo.py      # Invocation of sp_approve_admission
│   ├── dashboard_repo.py       # Live KPI & monthly aggregation queries
│   └── insights_repo.py        # Query Lab, EXPLAIN plan execution, Audit log
├── routes/                     # Thin Flask Blueprints (Validate -> Repo -> JSON/Render)
│   ├── auth_routes.py          # Login, session management & RBAC guards
│   ├── dashboard_routes.py     # Jobgio dashboard views & statistics API
│   ├── student_routes.py       # Student catalog & profile views
│   ├── academic_routes.py      # Courses, offerings, attendance, results
│   ├── fee_routes.py           # Payments & defaulter reports
│   └── insights_routes.py      # Viva showcase, query lab, EXPLAIN, audit log
├── templates/                  # Jinja2 HTML Templates
│   ├── base.html               # Jobgio floating shell, sidebar & navbar
│   ├── login.html              # Frosted light glass login card
│   ├── dashboard.html          # Stats row, Statistics chart, Pending approvals, Students table
│   ├── students/
│   │   ├── list.html           # Manage students table with sorting & filters
│   │   └── profile.html        # Comprehensive student dossier
│   ├── academics/
│   │   ├── offerings.html      # Course offerings & seat capacity gauges
│   │   ├── attendance.html     # Attendance roll-call grid
│   │   └── results.html        # Gradebook & marks entry
│   ├── fees/
│   │   └── ledger.html         # Payment receipts & defaulter list
│   ├── insights/
│   │   └── lab.html            # Viva Lab: ER diagram, Schema browser, Query Lab, EXPLAIN, Audit
│   └── components/
│       ├── stats_card.html     # Tall Jobgio stat card component
│       ├── sql_modal.html      # "Show SQL" inspection modal
│       └── toast.html          # Interactive toast notifications
├── static/
│   ├── css/
│   │   ├── tokens.css          # Design tokens (colors, radiuses, shadows, typography)
│   │   └── shell.css           # Shell layout, cards, pills, tables, chart styling
│   ├── js/
│   │   ├── dashboard.js        # KPI count-up animation & Chart.js configuration
│   │   ├── sql_inspector.js    # "Show SQL" modal populator
│   │   └── app.js              # Modals, slide-overs, toasts, active nav handling
│   └── img/                    # Logos, SVG icons, and demo student avatars
├── tests/                      # Pytest Automated Test Suite
│   ├── conftest.py             # Test database setup & teardown fixtures
│   ├── test_schema.py          # PK, FK, CHECK, UNIQUE constraint failure tests
│   ├── test_triggers.py        # Capacity limit, marks limit, and audit tests
│   ├── test_procedures.py      # Stored procedures atomicity & rollback tests
│   ├── test_concurrency.py     # Threaded seat-overselling race condition test
│   ├── test_queries.py         # Verification of 25 showcase queries
│   └── test_security.py        # SQL injection immunity & RBAC 403 enforcement
├── scripts/
│   ├── backup.sh               # mysqldump backup automation script
│   └── restore.sh              # Database restoration script
└── docs/
    ├── DESIGN_DOCUMENT.md      # Full Stage A Specification Document
    ├── er_diagram.md           # Mermaid & ASCII ER diagrams
    ├── normalization.md        # Mathematical normalization walkthrough
    └── README.md               # Quickstart, credentials, and viva defense guide
```

---

## 7.2 Milestone Sequence (M0 to M10)

- **M0: Formal Architecture & Schema Specification (Current Milestone)**
  - *Deliverable*: Deliver Phases 1-7 and Pre-Mortem in complete detail. Commit design docs to `docs/`.
  - *Acceptance Gate*: Await user explicit confirmation ("proceed").
- **M1: Database Schema & Constraint Verification**
  - *Deliverable*: Create `db/schema.sql` and run `test_schema.py`.
  - *Acceptance Gate*: 100% pass on all constraint rejection tests (CHECK, UNIQUE, FK, NOT NULL).
- **M2: Triggers, Stored Routines & Views**
  - *Deliverable*: Implement `triggers.sql`, `procedures.sql`, `views.sql`.
  - *Acceptance Gate*: `test_triggers.py` and `test_procedures.py` pass; atomicity and rollback proven.
- **M3: Deterministic Seed Data & Showcase Queries**
  - *Deliverable*: Implement `seed.py` (300+ students, 60 offerings, 1500+ enrollments); execute all 25 queries.
  - *Acceptance Gate*: All 25 queries execute cleanly with expected row shapes and non-zero counts.
- **M4: Flask Backend Skeleton & Connection Pool**
  - *Deliverable*: Configure `app.py`, connection pooling, authentication routes, and parameterized repositories.
  - *Acceptance Gate*: Health check endpoint returns 200; auth token generation works.
- **M5: UI Shell & Jobgio Design Tokens**
  - *Deliverable*: Implement `tokens.css`, floating app shell, sidebar navigation, and base template.
  - *Acceptance Gate*: Visual layout matches Jobgio reference screenshot at 1440x900 resolution.
- **M6: Interactive Dashboard Implementation**
  - *Deliverable*: Build KPI cards, Chart.js statistics chart, pending approvals, and manage students table.
  - *Acceptance Gate*: Live SQL aggregates power count-up numbers; pending approvals can be accepted live.
- **M7: Core CRUD & Management Pages**
  - *Deliverable*: Build Students, Faculty, Departments, and Courses views with slide-over forms.
  - *Acceptance Gate*: Full CRUD operational; input validation rejects bad inputs both client-side and server-side.
- **M8: Academic & Financial Workflows**
  - *Deliverable*: Enrollments, Attendance roll-call, Results gradebook, and Fee payments.
  - *Acceptance Gate*: UI surfaces exact trigger error messages on full capacity and marks overflow.
- **M9: Viva Defense & DB Insights Lab**
  - *Deliverable*: Interactive ER diagram browser, Schema inspector, Query Lab with EXPLAIN, Transaction demo, and Audit log.
  - *Acceptance Gate*: Live execution of showcase queries with graphical EXPLAIN execution plans.
- **M10: Backup/Restore Scripts, Documentation & Self-Audit**
  - *Deliverable*: Write `backup.sh`, `restore.sh`, `README.md`, and produce final self-audit checklist.
  - *Acceptance Gate*: Clean execution of full test suite and clean fresh-install run.

---

## 7.3 Pytest Automated Verification Matrix (`tests/`)

Every database guarantee will be verified using `pytest` against an isolated test database instance:

| Test Module | Test Case ID | Test Objective | Assertion & Expected Behavior |
|---|---|---|---|
| `test_schema.py` | `test_chk_student_age` | Insert student younger than 15 years old | Rejection with `IntegrityError` (CHECK constraint violation). |
| `test_schema.py` | `test_uk_student_roll` | Insert duplicate student roll number | Rejection with `IntegrityError` (Duplicate entry for key `uk_student_roll`). |
| `test_schema.py` | `test_chk_course_credits` | Insert course with credits = 7 | Rejection with `IntegrityError` (`credits BETWEEN 1 AND 6`). |
| `test_schema.py` | `test_fk_restrict_dept_delete`| Delete department with active students | Rejection with `IntegrityError` (Cannot delete parent row, FK constraint). |
| `test_triggers.py` | `test_trg_capacity_limit` | Direct INSERT into enrollment when capacity full | Rejection with `SQLSTATE '45000'` ("maximum seating capacity reached"). |
| `test_triggers.py` | `test_trg_enrolled_count_sync`| Verify `enrolled_count` after insert, update, delete | `enrolled_count` increments on insert, decrements on drop/delete. |
| `test_triggers.py` | `test_trg_marks_ceiling` | Insert marks_obtained = 105 for exam with max 100 | Rejection with `SQLSTATE '45000'` ("marks_obtained cannot exceed max_marks"). |
| `test_triggers.py` | `test_trg_audit_logging` | Update student status from Active to Suspended | New row appears in `audit_log` with correct JSON before/after state. |
| `test_procedures.py` | `test_sp_enroll_success` | Call `sp_enroll_student` on available seat | Returns status 200, row inserted in `enrollment`. |
| `test_procedures.py` | `test_sp_enroll_duplicate`| Call `sp_enroll_student` on existing enrollment | Returns status 409, message indicates already enrolled. |
| `test_procedures.py` | `test_sp_approve_atomic_abort`| Force failure during `sp_approve_admission` | Zero rows committed in `student` or `app_user` (ACID Rollback). |
| `test_procedures.py` | `test_sp_payment_overpayment`| Pay fee amount exceeding semester fee due | Returns status 400, message indicates overpayment rejected. |
| `test_concurrency.py`| `test_race_condition_last_seat`| Launch 2 concurrent threads on 1 remaining seat | Exactly one thread receives 200 (Enrolled); one receives 409 (Full). |
| `test_queries.py` | `test_showcase_queries_25` | Execute queries Q01 through Q25 on seed data | All 25 queries return non-empty datasets with expected schema. |
| `test_security.py` | `test_sql_injection_defense` | Pass `' OR '1'='1` into search and sort params | Treated strictly as literal string; zero unauthorized rows leaked. |
| `test_security.py` | `test_rbac_access_control` | Student user requests faculty grading endpoint | HTTP 403 Forbidden returned by role middleware. |

---

# HARD STOP: READY FOR PHASE A APPROVAL
Phases 1 through 7 and the comprehensive pre-mortem are fully formulated, academically justified, and committed to disk.

Awaiting your review and explicit instruction **"proceed"** before commencing Stage B implementation.
