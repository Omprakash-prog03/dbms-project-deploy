from repositories.db_pool import db_pool
import datetime

class AttendanceRepository:
    @staticmethod
    def get_class_roster(offering_id, class_date=None):
        if not class_date:
            class_date = datetime.date.today().isoformat()

        sql = """
            SELECT e.enrollment_id, s.student_id, s.roll_no,
                   CONCAT(s.first_name, ' ', s.last_name) AS student_name,
                   d.dept_code, e.status AS enrollment_status,
                   a.attendance_id, a.status AS attendance_status,
                   fn_attendance_pct(e.enrollment_id) AS current_attendance_pct
            FROM enrollment e
            JOIN student s ON e.student_id = s.student_id
            JOIN department d ON s.dept_id = d.dept_id
            LEFT JOIN attendance a ON e.enrollment_id = a.enrollment_id AND a.class_date = %s
            WHERE e.offering_id = %s AND e.status = 'Enrolled'
            ORDER BY s.roll_no ASC
        """
        return db_pool.execute_query(sql, (class_date, offering_id), fetch="all")

    @staticmethod
    def save_batch(offering_id, class_date, records):
        """
        Records attendance for the whole class list in one atomic transaction.
        records: list of dicts [{'enrollment_id': int, 'status': 'Present'|'Absent'|'Late'}]
        """
        try:
            day = datetime.date.fromisoformat(class_date)
        except (ValueError, TypeError):
            raise ValueError("Choose a valid class date.")
        if day > datetime.date.today():
            raise ValueError("Attendance cannot be recorded for a future date.")
        if not isinstance(records, list) or not records or len(records) > 1000:
            raise ValueError("Provide between 1 and 1,000 attendance records.")
        seen = set()
        for record in records:
            enrollment_id = int(record["enrollment_id"])
            if enrollment_id in seen:
                raise ValueError("Each student can appear only once on a roll-call sheet.")
            seen.add(enrollment_id)
            if record["status"] not in ("Present", "Absent", "Late"):
                raise ValueError("Choose Present, Absent, or Late.")
        with db_pool.get_connection() as conn:
            cur = conn.cursor()
            try:
                if not db_pool.is_mysql:
                    cur.execute("BEGIN IMMEDIATE TRANSACTION;")
                else:
                    cur.execute("START TRANSACTION;")

                for rec in records:
                    enr_id = rec["enrollment_id"]
                    status = rec["status"]

                    # Never accept another class's enrollment, even if an ID is forged.
                    cur.execute(
                        "SELECT status, offering_id FROM enrollment WHERE enrollment_id = ?" if not db_pool.is_mysql else
                        "SELECT status, offering_id FROM enrollment WHERE enrollment_id = %s FOR UPDATE", (enr_id,))
                    row = cur.fetchone()
                    if not row:
                        raise ValueError("Enrollment does not exist.")
                    state = row[0] if not db_pool.is_mysql else row["status"]
                    course = row[1] if not db_pool.is_mysql else row["offering_id"]
                    if state != "Enrolled" or course != offering_id:
                        raise ValueError("Attendance requires an active enrollment in the selected offering.")

                    # Delete existing if any for this day, then insert
                    cur.execute(
                        "DELETE FROM attendance WHERE enrollment_id = ? AND class_date = ?" if not db_pool.is_mysql else
                        "DELETE FROM attendance WHERE enrollment_id = %s AND class_date = %s",
                        (enr_id, class_date)
                    )
                    cur.execute(
                        "INSERT INTO attendance (enrollment_id, class_date, status) VALUES (?, ?, ?)" if not db_pool.is_mysql else
                        "INSERT INTO attendance (enrollment_id, class_date, status) VALUES (%s, %s, %s)",
                        (enr_id, class_date, status)
                    )
                conn.commit()
                return {"success": True, "count": len(records)}
            except Exception as e:
                conn.rollback()
                raise e
            finally:
                cur.close()

    @staticmethod
    def get_summary_by_offering(offering_id):
        sql = """
            SELECT
                COUNT(a.attendance_id) AS total_logs,
                SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) AS present_count,
                SUM(CASE WHEN a.status = 'Late' THEN 1 ELSE 0 END) AS late_count,
                SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) AS absent_count,
                COUNT(DISTINCT a.class_date) AS total_classes_conducted
            FROM enrollment e
            JOIN attendance a ON e.enrollment_id = a.enrollment_id
            WHERE e.offering_id = %s
        """
        return db_pool.execute_query(sql, (offering_id,), fetch="one")
