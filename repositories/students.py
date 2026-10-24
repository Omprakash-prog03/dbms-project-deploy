from repositories.db_pool import db_pool

class StudentRepository:
    # Allow-listed columns for safe sorting
    ALLOWED_SORT_COLUMNS = {
        "roll_no": "s.roll_no",
        "name": "full_name",
        "dept_code": "d.dept_code",
        "current_semester": "s.current_semester",
        "status": "s.status",
        "admission_date": "s.admission_date",
        "average_marks": "average_marks"
    }

    @staticmethod
    def get_all(search=None, dept_id=None, status=None, sort_col="roll_no", sort_dir="asc", page=1, per_page=15):
        page = max(1, int(page or 1))
        if per_page is not None:
            per_page = max(1, min(500, int(per_page)))
        # Validate sort column and direction against allowlists
        order_col = StudentRepository.ALLOWED_SORT_COLUMNS.get(sort_col, "s.roll_no")
        order_dir = "ASC" if str(sort_dir).upper() == "ASC" else "DESC"

        where_clauses = ["1=1"]
        params = []

        if search:
            where_clauses.append("(s.roll_no LIKE %s OR s.first_name LIKE %s OR s.last_name LIKE %s OR s.email LIKE %s OR CONCAT(s.first_name, ' ', s.last_name) LIKE %s)")
            like_term = f"%{search}%"
            params.extend([like_term] * 5)

        if dept_id:
            where_clauses.append("s.dept_id = %s")
            params.append(dept_id)

        if status and status != "All":
            where_clauses.append("s.status = %s")
            params.append(status)

        where_sql = " AND ".join(where_clauses)

        # Count total matching rows
        count_sql = f"""
            SELECT COUNT(*)
            FROM student s
            JOIN department d ON s.dept_id = d.dept_id
            WHERE {where_sql}
        """
        total = db_pool.execute_query(count_sql, tuple(params), fetch="val") or 0

        # Paginated fetch from v_student_overview
        pages = max(1, (total + per_page - 1) // per_page) if per_page else 1
        page = min(page, pages)
        offset = (page - 1) * per_page if per_page else 0
        query_sql = f"""
            SELECT
                s.student_id,
                s.roll_no,
                s.first_name,
                s.last_name,
                CONCAT(s.first_name, ' ', s.last_name) AS full_name,
                s.email,
                s.phone,
                s.gender,
                s.dob,
                s.address,
                s.current_semester,
                s.status,
                s.admission_date,
                d.dept_id,
                d.dept_code,
                d.dept_name,
                COUNT(DISTINCT e.offering_id) AS total_courses_enrolled,
                ROUND(COALESCE(AVG(r.marks_obtained), 0), 2) AS average_marks
            FROM student s
            JOIN department d ON s.dept_id = d.dept_id
            LEFT JOIN enrollment e ON s.student_id = e.student_id AND e.status = 'Enrolled'
            LEFT JOIN result r ON e.enrollment_id = r.enrollment_id
            WHERE {where_sql}
            GROUP BY s.student_id, d.dept_id, s.admission_date
            ORDER BY {order_col} {order_dir}, s.student_id ASC
        """
        if per_page:
            query_sql += " LIMIT %s OFFSET %s"
        page_params = tuple(params + ([per_page, offset] if per_page else []))
        rows = db_pool.execute_query(query_sql, page_params, fetch="all")
        for row in rows:
            for field in ("dob", "admission_date"):
                row[field] = str(row[field]) if row[field] else ""

        return {
            "items": rows,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": pages
        }

    @staticmethod
    def get_by_id(student_id):
        sql = """
            SELECT s.*, d.dept_code, d.dept_name,
                   CONCAT(s.first_name, ' ', s.last_name) AS full_name,
                   fn_student_cgpa(s.student_id) AS cgpa
            FROM student s
            JOIN department d ON s.dept_id = d.dept_id
            WHERE s.student_id = %s
        """
        return db_pool.execute_query(sql, (student_id,), fetch="one")

    @staticmethod
    def get_by_roll_no(roll_no):
        sql = """
            SELECT s.*, d.dept_code, d.dept_name,
                   CONCAT(s.first_name, ' ', s.last_name) AS full_name,
                   fn_student_cgpa(s.student_id) AS cgpa
            FROM student s
            JOIN department d ON s.dept_id = d.dept_id
            WHERE s.roll_no = %s
        """
        return db_pool.execute_query(sql, (roll_no,), fetch="one")

    @staticmethod
    def get_attendance_summary(student_id):
        sql = """
            SELECT course_code, course_title, academic_year, term,
                   COALESCE(total_classes, 0) AS total_classes,
                   COALESCE(present_count, 0) AS present_count,
                   COALESCE(late_count, 0) AS late_count,
                   COALESCE(absent_count, 0) AS absent_count,
                   COALESCE(attendance_percentage, 0) AS attendance_percentage
            FROM v_attendance_summary
            WHERE student_id = %s
            ORDER BY course_code ASC
        """
        return db_pool.execute_query(sql, (student_id,), fetch="all")

    @staticmethod
    def faculty_can_access(student_id, faculty_id):
        if not faculty_id:
            return False
        return bool(db_pool.execute_query(
            """SELECT COUNT(*) FROM enrollment e
               JOIN course_offering co ON e.offering_id = co.offering_id
               WHERE e.student_id = %s AND co.faculty_id = %s""",
            (student_id, faculty_id), fetch='val'))

    @staticmethod
    def get_guardians(student_id):
        sql = "SELECT * FROM guardian WHERE student_id = %s ORDER BY guardian_id ASC"
        return db_pool.execute_query(sql, (student_id,), fetch="all")

    @staticmethod
    def get_enrollments(student_id):
        sql = """
            SELECT e.enrollment_id, e.enroll_date, e.status AS enrollment_status, e.status,
                   co.offering_id, co.academic_year, co.term,
                   c.course_code, c.title AS course_title, c.title, c.credits, c.semester_no,
                   CONCAT(f.first_name, ' ', f.last_name) AS instructor_name,
                   CONCAT(f.first_name, ' ', f.last_name) AS faculty_name,
                   fn_attendance_pct(e.enrollment_id) AS attendance_percentage,
                   fn_attendance_pct(e.enrollment_id) AS attendance_pct
            FROM enrollment e
            JOIN course_offering co ON e.offering_id = co.offering_id
            JOIN course c ON co.course_id = c.course_id
            JOIN faculty f ON co.faculty_id = f.faculty_id
            WHERE e.student_id = %s
            ORDER BY co.academic_year DESC, c.course_code ASC
        """
        return db_pool.execute_query(sql, (student_id,), fetch="all")

    @staticmethod
    def get_results(student_id):
        sql = """
            SELECT c.course_code, c.title AS course_title, c.title,
                   ex.exam_type, ex.exam_date, ex.max_marks, r.marks_obtained,
                   ROUND((1.0 * r.marks_obtained / ex.max_marks) * 100, 1) AS percentage,
                   fn_grade(ROUND((1.0 * r.marks_obtained / ex.max_marks) * 100, 1)) AS grade
            FROM enrollment e
            JOIN course_offering co ON e.offering_id = co.offering_id
            JOIN course c ON co.course_id = c.course_id
            JOIN exam ex ON co.offering_id = ex.offering_id
            JOIN result r ON ex.exam_id = r.exam_id AND e.enrollment_id = r.enrollment_id
            WHERE e.student_id = %s
            ORDER BY c.course_code ASC, ex.exam_type ASC
        """
        return db_pool.execute_query(sql, (student_id,), fetch="all")

    @staticmethod
    def get_fee_summary(student_id):
        sql = """
            SELECT
                fs.semester_no,
                fs.amount AS total_fee,
                ROUND(COALESCE(SUM(fp.amount), 0), 2) AS total_paid,
                ROUND(fs.amount - ROUND(COALESCE(SUM(fp.amount), 0), 2), 2) AS balance_due,
                CASE
                    WHEN ROUND(fs.amount - ROUND(COALESCE(SUM(fp.amount), 0), 2), 2) > 0 THEN 1
                    ELSE 0
                END AS is_defaulter,
                CASE
                    WHEN ROUND(COALESCE(SUM(fp.amount), 0), 2) >= fs.amount THEN 'Fully Paid'
                    WHEN ROUND(COALESCE(SUM(fp.amount), 0), 2) > 0 THEN 'Partial'
                    ELSE 'Unpaid'
                END AS payment_status
            FROM student s
            JOIN department d ON s.dept_id = d.dept_id
            JOIN fee_structure fs ON d.dept_id = fs.dept_id AND fs.semester_no <= s.current_semester
            LEFT JOIN fee_payment fp ON s.student_id = fp.student_id AND fs.semester_no = fp.semester_no
            WHERE s.student_id = %s
            GROUP BY s.student_id, fs.semester_no, fs.amount
            ORDER BY fs.semester_no ASC
        """
        return db_pool.execute_query(sql, (student_id,), fetch="all")

    @staticmethod
    def create(roll_no, first_name, last_name, email, phone, dob, gender, address, dept_id, admission_date, current_semester=1, status='Active', photo_url=None):
        sql = """
            INSERT INTO student (
                roll_no, first_name, last_name, email, phone,
                dob, gender, address, dept_id, admission_date,
                current_semester, status, photo_url
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = (roll_no, first_name, last_name, email, phone, dob, gender, address, dept_id, admission_date, current_semester, status, photo_url)
        res = db_pool.execute_dml(sql, params)

        return res["lastrowid"]

    @staticmethod
    def create_with_portal(roll_no, first_name, last_name, email, phone, dob, gender, address, dept_id,
                           admission_date, password, current_semester=1, status='Active', photo_url=None):
        """Create the student and their portal login in one transaction, using the chosen password."""
        from repositories.accounts import create_account, sql
        with db_pool.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('START TRANSACTION' if db_pool.is_mysql else 'BEGIN IMMEDIATE')
                cursor.execute(sql("""
                    INSERT INTO student (roll_no, first_name, last_name, email, phone, dob, gender,
                                         address, dept_id, admission_date, current_semester, status, photo_url)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """), (roll_no, first_name, last_name, email, phone, dob, gender, address, dept_id,
                       admission_date, current_semester, status, photo_url))
                student_id = cursor.lastrowid
                username = create_account(cursor, roll_no, password, 'student', student_id=student_id)
                conn.commit()
                return student_id, username
            except Exception:
                conn.rollback()
                raise
            finally:
                cursor.close()

    @staticmethod
    def update(student_id, first_name, last_name, email, phone, address, current_semester, status,
               dept_id=None, dob=None, gender=None, admission_date=None):
        existing = StudentRepository.get_by_id(student_id)
        if not existing:
            raise ValueError("Student record not found.")
        # Changing department after payments would silently change fee balances.
        if dept_id is not None and int(dept_id) != existing["dept_id"]:
            if db_pool.execute_query("SELECT COUNT(*) FROM fee_payment WHERE student_id = %s", (student_id,), fetch="val"):
                raise ValueError("A student with recorded payments cannot change department. Reconcile the fee ledger first.")
        sql = """UPDATE student SET first_name=%s, last_name=%s, email=%s, phone=%s, address=%s,
                 current_semester=%s, status=%s, dept_id=%s, dob=%s, gender=%s, admission_date=%s WHERE student_id=%s"""
        params = (first_name, last_name, email, phone, address, current_semester, status,
                  dept_id if dept_id is not None else existing["dept_id"],
                  dob if dob is not None else existing["dob"],
                  gender if gender is not None else existing["gender"],
                  admission_date if admission_date is not None else existing["admission_date"], student_id)
        return db_pool.execute_dml(sql, params)["rowcount"]

    @staticmethod
    def delete(student_id):
        if not StudentRepository.get_by_id(student_id):
            raise ValueError("Student record not found.")
        return db_pool.execute_dml("DELETE FROM student WHERE student_id = %s", (student_id,))["rowcount"]
