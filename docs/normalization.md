# Normalization Walkthrough: Student Information Management System (SIMS)

## 1. Objectives & Theory
Database normalization systematically decomposes tables to eliminate data redundancy and insertion, update, and deletion anomalies while ensuring lossless joins and dependency preservation.

This document walks through the normalization of an unnormalized flat university record table into Third Normal Form (3NF) and verifies Boyce-Codd Normal Form (BCNF) compliance.

---

## 2. Unnormalized Form (UNF)
Consider a legacy flat spreadsheet or denormalized reporting table commonly found in poorly designed university systems:

### `UNNORMALIZED_STUDENT_COURSE_MARKS` Table

| Column Name | Sample Value 1 | Sample Value 2 |
|---|---|---|
| roll_no | "24CS101" | "24EC202" |
| student_name | "Aarav Sharma" | "Priya Nair" |
| student_email | "aarav@sims.edu" | "priya@sims.edu" |
| student_dob | "2004-05-14" | "2005-02-19" |
| dept_code | "CSE" | "ECE" |
| dept_name | "Computer Science & Engineering" | "Electronics & Comm. Eng." |
| hod_name | "Dr. Rajesh Verma" | "Dr. Sunita Rao" |
| course_codes | {"CS201", "CS202"} *(repeating group)* | {"EC201", "EC202"} |
| course_titles | {"Data Structures", "Database Systems"} | {"Signals & Systems", "Digital Circuits"} |
| faculty_names | {"Prof. Alan", "Prof. Barbara"} | {"Prof. Charles", "Prof. Diana"} |
| marks_obtained | {88.5, 92.0} | {75.0, 84.5} |
| guardian_contacts | {"Suresh (Father, 9876543210)", "Meena (Mother, 9876543211)"} | {"Ramesh (Father, 9123456780)"} |

### Anomalies in UNF:
1. **Multi-valued Attributes & Repeating Groups**: Multiple courses, guardians, and marks are packed inside single columns or variable-length lists.
2. **Insertion Anomaly**: We cannot record a new department or catalog course until a student enrolls in it.
3. **Update Anomaly**: If a department changes its HoD or name, hundreds of student rows must be updated; any missed row creates inconsistent data.
4. **Deletion Anomaly**: If the only student taking "EC202" drops out, the course details and instructor information are lost entirely.

---

## 3. First Normal Form (1NF)

### 1NF Definition:
A relation is in **First Normal Form (1NF)** if and only if all underlying domains contain only **atomic (indivisible) values**, and there are no repeating groups or arrays.

### Transformation to 1NF:
We flatten the repeating groups so that each row represents exactly one student taking one course evaluation, and separate guardian contacts into their own relation.

The flattened relation becomes:
`R_1NF (roll_no, student_name, student_email, student_dob, dept_code, dept_name, hod_faculty_name, course_code, course_title, academic_year, term, faculty_name, exam_type, max_marks, marks_obtained)`

### Candidate Key for `R_1NF`:
Because a student can take multiple courses, and each course has multiple exams (e.g., Midterm, Final) in a given academic term, the primary composite key must be:
$$\text{Composite PK} = \{\text{roll\_no}, \text{course\_code}, \text{academic\_year}, \text{term}, \text{exam\_type}\}$$

### Identified Functional Dependencies (FDs):
- **FD1**: `roll_no` $\to$ `student_name`, `student_email`, `student_dob`, `dept_code`
- **FD2**: `dept_code` $\to$ `dept_name`, `hod_faculty_name`
- **FD3**: `course_code` $\to$ `course_title`, `dept_code`
- **FD4**: `course_code`, `academic_year`, `term` $\to$ `faculty_name`
- **FD5**: `course_code`, `academic_year`, `term`, `exam_type` $\to$ `max_marks`
- **FD6**: `roll_no`, `course_code`, `academic_year`, `term`, `exam_type` $\to$ `marks_obtained`

---

## 4. Second Normal Form (2NF)

### 2NF Definition:
A relation is in **Second Normal Form (2NF)** if and only if it is in 1NF and **no non-prime attribute is partially dependent on any candidate key**. Every non-prime attribute must depend on the *whole* candidate key.

### Identifying Partial Dependencies:
In `R_1NF`, the candidate key is `(roll_no, course_code, academic_year, term, exam_type)`.
- In FD1, non-prime attributes `(student_name, student_email, student_dob, dept_code)` depend *only* on `roll_no` (a proper subset of the key). **Partial dependency!**
- In FD3, `course_title` depends *only* on `course_code`. **Partial dependency!**
- In FD4, `faculty_name` depends on `(course_code, academic_year, term)`. **Partial dependency!**
- In FD5, `max_marks` depends on `(course_code, academic_year, term, exam_type)`. **Partial dependency!**

### Decomposition into 2NF:
We decompose `R_1NF` into distinct relations based on the determinant of each partial dependency:

1. **`R_STUDENT_BASE`**:
   - Attributes: `(roll_no, student_name, student_email, student_dob, dept_code, dept_name, hod_faculty_name)`
   - Primary Key: `roll_no`
   - All non-prime attributes depend fully on `roll_no`.

2. **`R_COURSE_BASE`**:
   - Attributes: `(course_code, course_title, dept_code)`
   - Primary Key: `course_code`
   - `course_title` and `dept_code` depend fully on `course_code`.

3. **`R_OFFERING_BASE`**:
   - Attributes: `(course_code, academic_year, term, faculty_name)`
   - Primary Key: `(course_code, academic_year, term)`
   - `faculty_name` depends fully on the composite key.

4. **`R_EXAM_BASE`**:
   - Attributes: `(course_code, academic_year, term, exam_type, max_marks)`
   - Primary Key: `(course_code, academic_year, term, exam_type)`
   - `max_marks` depends fully on the composite key.

5. **`R_RESULT_BASE`**:
   - Attributes: `(roll_no, course_code, academic_year, term, exam_type, marks_obtained)`
   - Primary Key: `(roll_no, course_code, academic_year, term, exam_type)`
   - `marks_obtained` depends fully on the full composite key.

All relations are now in **2NF**.

---

## 5. Third Normal Form (3NF)

### 3NF Definition:
A relation is in **Third Normal Form (3NF)** if and only if it is in 2NF and **no non-prime attribute is transitively dependent on the primary key** (i.e., for every non-trivial FD $X \to Y$, either $X$ is a superkey or $Y$ is a prime attribute). In simple terms: "Every non-key attribute must depend on the key, the whole key, and nothing but the key."

### Identifying Transitive Dependencies:
Examine `R_STUDENT_BASE`:
- `roll_no` $\to$ `dept_code`
- `dept_code` $\to$ `dept_name`, `hod_faculty_name`
- Therefore: `roll_no` $\to$ `dept_name`, `hod_faculty_name` is a **transitive dependency** through `dept_code`.
- `dept_code` is NOT a superkey of `R_STUDENT_BASE`, and `dept_name` is non-prime.

Examine `R_OFFERING_BASE`:
- `faculty_name` (or `faculty_id`) has attributes such as `email`, `designation`, and `salary` that depend on the instructor, not the course offering itself.

### Decomposition into 3NF:
We extract intermediate determinants into their own relational tables:

1. **`DEPARTMENT`**:
   - Attributes: `(dept_id, dept_code, dept_name, hod_faculty_id, established_year)`
   - Primary Key: `dept_id`
   - Candidate Key: `dept_code`
   - FDs: `dept_id` $\to$ `dept_code`, `dept_name`, `hod_faculty_id`, `established_year` (Determinant is superkey).

2. **`FACULTY`**:
   - Attributes: `(faculty_id, first_name, last_name, email, phone, dept_id, designation, hire_date, salary, status)`
   - Primary Key: `faculty_id`
   - Candidate Key: `email`
   - FDs: `faculty_id` $\to$ all other attributes.

3. **`STUDENT`**:
   - Attributes: `(student_id, roll_no, first_name, last_name, email, phone, dob, gender, address, dept_id, admission_date, current_semester, status, photo_url)`
   - Primary Key: `student_id`
   - Candidate Key: `roll_no`, `email`
   - FDs: `student_id` $\to$ all personal and departmental attributes. Transitive dependency eliminated via `dept_id FK`.

4. **`COURSE`**:
   - Attributes: `(course_id, course_code, title, credits, dept_id, semester_no)`
   - Primary Key: `course_id`
   - Candidate Key: `course_code`
   - FDs: `course_id` $\to$ all course attributes.

5. **`COURSE_OFFERING`**:
   - Attributes: `(offering_id, course_id, faculty_id, academic_year, term, capacity, enrolled_count)`
   - Primary Key: `offering_id`
   - Candidate Key: `(course_id, academic_year, term)`
   - FDs: `offering_id` $\to$ `course_id`, `faculty_id`, `academic_year`, `term`, `capacity`.

6. **`ENROLLMENT`** (Junction Table):
   - Attributes: `(enrollment_id, student_id, offering_id, enroll_date, status)`
   - Primary Key: `enrollment_id`
   - Candidate Key: `(student_id, offering_id)`
   - FDs: `enrollment_id` $\to$ `student_id`, `offering_id`, `enroll_date`, `status`.

7. **`EXAM`**:
   - Attributes: `(exam_id, offering_id, exam_type, max_marks, exam_date)`
   - Primary Key: `exam_id`
   - Candidate Key: `(offering_id, exam_type)`
   - FDs: `exam_id` $\to$ `offering_id`, `exam_type`, `max_marks`, `exam_date`.

8. **`RESULT`**:
   - Attributes: `(result_id, exam_id, enrollment_id, marks_obtained)`
   - Primary Key: `result_id`
   - Candidate Key: `(exam_id, enrollment_id)`
   - FDs: `result_id` $\to$ `exam_id`, `enrollment_id`, `marks_obtained`.

All decomposed tables are strictly in **Third Normal Form (3NF)**.

---

## 6. Boyce-Codd Normal Form (BCNF) Analysis

### BCNF Definition:
A relation is in **BCNF** if for every non-trivial functional dependency $X \to Y$, the determinant $X$ is a **superkey**.

### Table-by-Table BCNF Audit:
1. `DEPARTMENT`: Candidate keys are `dept_id` and `dept_code`. Every FD determinant is a superkey. **Holds BCNF.**
2. `FACULTY`: Candidate keys are `faculty_id` and `email`. All determinants are superkeys. **Holds BCNF.**
3. `STUDENT`: Candidate keys are `student_id`, `roll_no`, `email`. All determinants are superkeys. **Holds BCNF.**
4. `COURSE`: Candidate keys are `course_id` and `course_code`. All determinants are superkeys. **Holds BCNF.**
5. `COURSE_OFFERING`: Candidate keys are `offering_id` and `(course_id, academic_year, term)`. All determinants are superkeys. **Holds BCNF.**
6. `ENROLLMENT`: Candidate keys are `enrollment_id` and `(student_id, offering_id)`. All determinants are superkeys. **Holds BCNF.**
7. `EXAM`: Candidate keys are `exam_id` and `(offering_id, exam_type)`. All determinants are superkeys. **Holds BCNF.**
8. `RESULT`: Candidate keys are `result_id` and `(exam_id, enrollment_id)`. All determinants are superkeys. **Holds BCNF.**
9. `FEE_STRUCTURE`: Candidate key is `(dept_id, semester_no)`. Determinant is the entire primary key. **Holds BCNF.**
10. `FEE_PAYMENT`: Candidate keys are `payment_id` and `receipt_no`. All determinants are superkeys. **Holds BCNF.**

**Conclusion**: The relational schema is not only in 3NF, but also strictly satisfies **BCNF** because there are no overlapping composite candidate keys with cross-dependent non-trivial determinants.

---

## 7. Justified Denormalization & Consistency Triggers

### Column: `course_offering.enrolled_count`
- **Why Denormalized?**
  In a high-concurrency registration system, checking if an offering is full requires verifying capacity against the count of active enrollments. If calculated on the fly via `COUNT(*) FROM enrollment WHERE offering_id = ? AND status = 'Enrolled'`, every registration and dashboard view incurs an aggregate lock or sequential scan over thousands of rows. Maintaining a localized integer `enrolled_count` allows:
  1. $O(1)$ constant time capacity checks.
  2. Safe row-level locking via `SELECT capacity, enrolled_count FROM course_offering WHERE offering_id = ? FOR UPDATE`.
  3. Blazing fast dashboard and catalog listings without N+1 aggregation queries.

- **Trigger Maintenance for Absolute Consistency**:
  To guarantee that `enrolled_count` never drifts from reality, three dedicated database triggers maintain it atomically:

```sql
-- 1. When a new enrollment is created with status 'Enrolled'
DELIMITER $$
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

-- 2. When enrollment status changes (e.g. Enrolled -> Dropped, or Dropped -> Enrolled)
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

-- 3. When an enrollment row is deleted directly
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
DELIMITER ;
```
With these triggers operating inside the same ACID transaction boundary as the DML statement, `enrolled_count` is mathematically guaranteed to equal `COUNT(*) WHERE status = 'Enrolled'`.
