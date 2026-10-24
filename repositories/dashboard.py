from repositories.db_pool import db_pool
from datetime import date

class DashboardRepository:
    @staticmethod
    def get_stats():
        """
        Computes the 6 live KPI cards from database aggregates.
        Zero hardcoded numbers!
        """
        total_students = db_pool.execute_query("SELECT COUNT(*) FROM student", fetch="val") or 0
        total_departments = db_pool.execute_query("SELECT COUNT(*) FROM department", fetch="val") or 0
        active_courses = db_pool.execute_query("SELECT COUNT(DISTINCT course_id) FROM course_offering", fetch="val") or 0
        faculty_members = db_pool.execute_query("SELECT COUNT(*) FROM faculty WHERE status = 'Active'", fetch="val") or 0
        total_enrollments = db_pool.execute_query("SELECT COUNT(*) FROM enrollment WHERE status = 'Enrolled'", fetch="val") or 0
        pending_admissions = db_pool.execute_query("SELECT COUNT(*) FROM admission_application WHERE status = 'Pending'", fetch="val") or 0

        attendance = db_pool.execute_query("SELECT COUNT(*) AS total, COALESCE(SUM(CASE WHEN status IN ('Present','Late') THEN 1 ELSE 0 END),0) AS attended FROM attendance", fetch="one")
        payments = db_pool.execute_query("SELECT COUNT(*) AS total, ROUND(COALESCE(SUM(amount),0),2) AS collected FROM fee_payment", fetch="one")
        return {
            "total_courses": db_pool.execute_query("SELECT COUNT(*) FROM course", fetch="val") or 0,
            "total_offerings": db_pool.execute_query("SELECT COUNT(*) FROM course_offering", fetch="val") or 0,
            "attendance_records": attendance['total'],
            "attendance_pct": round(100 * attendance['attended'] / attendance['total'], 1) if attendance['total'] else 0,
            "total_collected": float(payments['collected']),
            "payment_count": payments['total'],
            "result_count": db_pool.execute_query("SELECT COUNT(*) FROM result", fetch="val") or 0,
            "total_students": total_students,
            "total_departments": total_departments,
            "active_courses": active_courses,
            "faculty_members": faculty_members,
            "total_enrollments": total_enrollments,
            "pending_admissions": pending_admissions
        }

    @staticmethod
    def get_monthly_chart(year=None):
        """
        Returns 12-month admissions vs enrollments from SQL aggregates.
        """
        year = year or date.today().year
        months_abbr = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        admissions = [0] * 12
        enrollments = [0] * 12

        # 1. Admissions by month
        adm_sql = """
            SELECT CAST(strftime('%m', admission_date) AS INTEGER) AS m, COUNT(*) AS cnt
            FROM student
            WHERE strftime('%Y', admission_date) = %s
            GROUP BY m
        """ if not db_pool.is_mysql else """
            SELECT MONTH(admission_date) AS m, COUNT(*) AS cnt
            FROM student
            WHERE YEAR(admission_date) = %s
            GROUP BY m
        """
        adm_rows = db_pool.execute_query(adm_sql, (str(year),), fetch="all")
        for r in adm_rows:
            m_idx = (r.get("m") or 1) - 1
            if 0 <= m_idx < 12:
                admissions[m_idx] = r.get("cnt") or 0

        # 2. Enrollments by month
        enr_sql = """
            SELECT CAST(strftime('%m', enroll_date) AS INTEGER) AS m, COUNT(*) AS cnt
            FROM enrollment
            WHERE strftime('%Y', enroll_date) = %s
            GROUP BY m
        """ if not db_pool.is_mysql else """
            SELECT MONTH(enroll_date) AS m, COUNT(*) AS cnt
            FROM enrollment
            WHERE YEAR(enroll_date) = %s
            GROUP BY m
        """
        enr_rows = db_pool.execute_query(enr_sql, (str(year),), fetch="all")
        for r in enr_rows:
            m_idx = (r.get("m") or 1) - 1
            if 0 <= m_idx < 12:
                enrollments[m_idx] = r.get("cnt") or 0

        return {
            "year": year,
            "labels": months_abbr,
            "admissions": admissions,
            "enrollments": enrollments
        }


    @staticmethod
    def get_chart_years():
        rows = db_pool.execute_query("SELECT DISTINCT YEAR(admission_date) AS year FROM student UNION SELECT DISTINCT YEAR(enroll_date) AS year FROM enrollment", fetch="all")
        return sorted({int(row["year"]) for row in rows if row["year"]} | {date.today().year}, reverse=True)
