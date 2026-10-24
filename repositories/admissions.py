from repositories.db_pool import db_pool
import datetime
import bcrypt
import secrets
import re

class AdmissionsRepository:
    @staticmethod
    def get_pending():
        sql = """
            SELECT aa.*, d.dept_code, d.dept_name
            FROM admission_application aa
            JOIN department d ON aa.dept_id = d.dept_id
            WHERE aa.status = 'Pending'
            ORDER BY aa.applied_on ASC
        """
        return db_pool.execute_query(sql, fetch="all")

    @staticmethod
    def create_application(applicant_name, email, phone, dept_id):
        name, email, phone = applicant_name.strip(), email.strip().lower(), phone.strip()
        if not name or len(name) > 100:
            raise ValueError('Enter an applicant name of at most 100 characters.')
        if len(email) > 100 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
            raise ValueError('Enter a valid applicant email address.')
        if not re.fullmatch(r'[+\d ()-]{7,20}', phone):
            raise ValueError('Enter a valid phone number.')
        dept_id = int(dept_id)
        with db_pool.get_connection() as conn:
            cursor = conn.cursor()
            def execute(sql, params):
                cursor.execute(sql if db_pool.is_mysql else sql.replace('%s', '?'), params)
            try:
                cursor.execute('START TRANSACTION' if db_pool.is_mysql else 'BEGIN IMMEDIATE')
                execute('SELECT dept_id FROM department WHERE dept_id=%s' + (' FOR UPDATE' if db_pool.is_mysql else ''), (dept_id,))
                if not cursor.fetchone():
                    raise ValueError('Choose an existing department.')
                execute('SELECT student_id FROM student WHERE LOWER(email)=%s', (email,))
                if cursor.fetchone():
                    raise ValueError('A student with that email is already registered.')
                execute("SELECT application_id FROM admission_application WHERE LOWER(email)=%s AND status='Pending'", (email,))
                if cursor.fetchone():
                    raise ValueError('An application with that email is already awaiting review.')
                execute("INSERT INTO admission_application (applicant_name,email,phone,dept_id,applied_on,status) VALUES (%s,%s,%s,%s,%s,'Pending')", (name,email,phone,dept_id,datetime.date.today().isoformat()))
                application_id = cursor.lastrowid
                conn.commit()
                return application_id
            except Exception:
                conn.rollback()
                raise
            finally:
                cursor.close()

    @staticmethod
    def approve_admission(application_id, reviewer_id=None, date_of_birth=None, address=""):
        """
        Implements sp_approve_admission transactional logic.
        """
        with db_pool.get_connection() as conn:
            cur = conn.cursor()
            try:
                if not db_pool.is_mysql:
                    cur.execute("BEGIN IMMEDIATE TRANSACTION;")
                else:
                    cur.execute("START TRANSACTION;")

                # Step 1: Check application
                cur.execute(
                    "SELECT applicant_name, email, phone, dept_id, status FROM admission_application WHERE application_id = ?" if not db_pool.is_mysql else
                    "SELECT applicant_name, email, phone, dept_id, status FROM admission_application WHERE application_id = %s FOR UPDATE",
                    (application_id,)
                )
                app_row = cur.fetchone()
                if not app_row:
                    conn.rollback()
                    return {"status_code": 404, "message": "Admission application not found."}

                name = app_row[0] if not db_pool.is_mysql else app_row["applicant_name"]
                email = app_row[1] if not db_pool.is_mysql else app_row["email"]
                phone = app_row[2] if not db_pool.is_mysql else app_row["phone"]
                dept_id = app_row[3] if not db_pool.is_mysql else app_row["dept_id"]
                status = app_row[4] if not db_pool.is_mysql else app_row["status"]

                if status != "Pending":
                    conn.rollback()
                    return {"status_code": 400, "message": f"Application cannot be processed. Current status: {status}"}

                # Do not invent a student's birth date when matriculating them.
                try:
                    birth = datetime.date.fromisoformat(str(date_of_birth or ""))
                except ValueError:
                    conn.rollback()
                    return {"status_code":400, "message":"Confirm the applicant's date of birth before approval."}
                today_date = datetime.date.today()
                age = today_date.year - birth.year - ((today_date.month, today_date.day) < (birth.month, birth.day))
                if age < 15:
                    conn.rollback()
                    return {"status_code":400, "message":"The applicant must be at least 15 years old."}

                # Parse name
                name_parts = name.strip().split(" ", 1)
                first_name = name_parts[0]
                last_name = name_parts[1] if len(name_parts) > 1 else "Scholar"

                # Generate Roll No: YY + DEPT_CODE + SEQ
                cur.execute(
                    "SELECT dept_code FROM department WHERE dept_id = ?" if not db_pool.is_mysql else
                    "SELECT dept_code FROM department WHERE dept_id = %s",
                    (dept_id,)
                )
                dept_code = (cur.fetchone()[0]) if not db_pool.is_mysql else cur.fetchone()["dept_code"]
                year_suffix = datetime.date.today().strftime("%y")

                # Serialize roll-number allocation on the department in MySQL.
                if db_pool.is_mysql:
                    cur.execute("SELECT dept_id FROM department WHERE dept_id = %s FOR UPDATE", (dept_id,))
                    cur.fetchone()
                prefix = f"{year_suffix}{dept_code}"
                cur.execute(
                    "SELECT roll_no FROM student WHERE roll_no LIKE ?" if not db_pool.is_mysql else
                    "SELECT roll_no FROM student WHERE roll_no LIKE %s",
                    (prefix + "%",)
                )
                suffixes = []
                for row in cur.fetchall():
                    existing = row[0] if not db_pool.is_mysql else row["roll_no"]
                    suffix = existing[len(prefix):]
                    if suffix.isdigit():
                        suffixes.append(int(suffix))
                roll_no = f"{prefix}{max(suffixes, default=0) + 1:03d}"

                # Insert Student
                today = datetime.date.today().isoformat()
                dob = birth.isoformat()
                cur.execute(
                    """INSERT INTO student (
                        roll_no, first_name, last_name, email, phone, dob, gender,
                        address, dept_id, admission_date, current_semester, status
                    ) VALUES (?, ?, ?, ?, ?, ?, 'Other', ?, ?, ?, 1, 'Active')""" if not db_pool.is_mysql else
                    """INSERT INTO student (
                        roll_no, first_name, last_name, email, phone, dob, gender,
                        address, dept_id, admission_date, current_semester, status
                    ) VALUES (%s, %s, %s, %s, %s, %s, 'Other', %s, %s, %s, 1, 'Active')""",
                    (roll_no, first_name, last_name, email, phone, dob, address[:500], dept_id, today)
                )
                student_id = cur.lastrowid

                # Provision user account
                temporary_password = secrets.token_urlsafe(12)
                pw_hash = bcrypt.hashpw(temporary_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
                cur.execute(
                    "INSERT INTO app_user (username, password_hash, role, student_id) VALUES (?, ?, 'student', ?)" if not db_pool.is_mysql else
                    "INSERT INTO app_user (username, password_hash, role, student_id) VALUES (%s, %s, 'student', %s)",
                    (roll_no.lower(), pw_hash, student_id)
                )

                # Update application status
                now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cur.execute(
                    "UPDATE admission_application SET status = 'Approved', reviewed_by = ?, reviewed_on = ? WHERE application_id = ?" if not db_pool.is_mysql else
                    "UPDATE admission_application SET status = 'Approved', reviewed_by = %s, reviewed_on = %s WHERE application_id = %s",
                    (reviewer_id, now_str, application_id)
                )

                # Audit log
                audit_json = db_pool._json_object("status", "Approved", "student_id", student_id, "roll_no", roll_no)
                cur.execute(
                    "INSERT INTO audit_log (table_name, action, record_id, new_values, changed_by) VALUES ('admission_application', 'UPDATE', ?, ?, 'admissions_officer')" if not db_pool.is_mysql else
                    "INSERT INTO audit_log (table_name, action, record_id, new_values, changed_by) VALUES ('admission_application', 'UPDATE', %s, %s, 'admissions_officer')",
                    (application_id, audit_json)
                )

                conn.commit()
                return {
                    "status_code": 200,
                    "message": "Admission approved. Student record and portal account created.",
                    "student_id": student_id,
                    "roll_no": roll_no,
                    "username": roll_no.lower(),
                    "temporary_password": temporary_password
                }
            except Exception as e:
                conn.rollback()
                return {"status_code": 500, "message": f"Transaction aborted: {str(e)}"}
            finally:
                cur.close()

    @staticmethod
    def reject_admission(application_id, reviewer_id=None):
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        res = db_pool.execute_dml("UPDATE admission_application SET status = 'Rejected', reviewed_by = %s, reviewed_on = %s WHERE application_id = %s AND status = 'Pending'", (reviewer_id, now_str, application_id))
        if not res["rowcount"]:
            return {"status_code":409, "message":"This application is no longer pending or does not exist."}
        return {"status_code":200, "message":"Application rejected."}

    @staticmethod
    def get_all(status="Pending", search=""):
        where = ["1=1"]
        params = []
        if status != "All":
            where.append("aa.status = %s")
            params.append(status)
        if search:
            where.append("(aa.applicant_name LIKE %s OR aa.email LIKE %s)")
            params.extend([f"%{search}%"] * 2)
        return db_pool.execute_query("SELECT aa.*, d.dept_code, d.dept_name FROM admission_application aa JOIN department d ON aa.dept_id = d.dept_id WHERE " + " AND ".join(where) + " ORDER BY aa.applied_on DESC, aa.application_id DESC", tuple(params), fetch="all")
