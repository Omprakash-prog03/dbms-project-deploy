"""Overall campus reports and PDF exports (shared by the UI and the download routes)."""
from datetime import date
from repositories.db_pool import db_pool
from config import Config
from repositories.dashboard import DashboardRepository
from repositories.pdf import Report
from repositories.students import StudentRepository


def _rows(sql, params=None):
    return db_pool.execute_query(sql, params, fetch='all') if params else db_pool.execute_query(sql, fetch='all')


def overview():
    """Figures shared by the HTML report page and the PDF summary."""
    stats = DashboardRepository.get_stats()
    by_department = _rows("""
        SELECT d.dept_code, d.dept_name, COUNT(s.student_id) AS students,
               COUNT(DISTINCT f.faculty_id) AS faculty
        FROM department d
        LEFT JOIN student s ON s.dept_id = d.dept_id
        LEFT JOIN faculty f ON f.dept_id = d.dept_id AND f.status = 'Active'
        GROUP BY d.dept_id, d.dept_code, d.dept_name
        ORDER BY d.dept_code
    """)
    by_status = _rows("SELECT status, COUNT(*) AS total FROM student GROUP BY status ORDER BY status")
    fee_status = _rows("""
        SELECT payment_status, COUNT(*) AS students, ROUND(COALESCE(SUM(balance_due), 0), 2) AS outstanding
        FROM v_fee_status GROUP BY payment_status ORDER BY payment_status
    """)
    grade_mix = _rows("""
        SELECT fn_grade(ROUND(100.0 * r.marks_obtained / ex.max_marks, 1)) AS grade, COUNT(*) AS total
        FROM result r JOIN exam ex ON r.exam_id = ex.exam_id
        GROUP BY grade ORDER BY grade
    """)
    return {
        'stats': stats,
        'by_department': by_department,
        'by_status': by_status,
        'fee_status': fee_status,
        'grade_mix': grade_mix,
        'generated': date.today(),
    }


def database_tables():
    """Physical tables and row counts. Administrators only; read-only."""
    if db_pool.is_mysql:
        names = [row['name'] for row in _rows(
            "SELECT table_name AS name FROM information_schema.tables "
            "WHERE table_schema = DATABASE() AND table_type = 'BASE TABLE' ORDER BY table_name"
        )]
    else:
        names = [row['name'] for row in _rows(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )]
    tables = []
    for name in names:
        if not name.replace('_', '').isalnum():
            continue
        count = db_pool.execute_query(f'SELECT COUNT(*) FROM {name}', fetch='val')
        tables.append({'name': name, 'rows': count or 0})
    return tables


def summary_report(financial=True, tables=None):
    data = overview()
    stats = data['stats']
    report = Report(
        f"{Config.PORTAL_NAME} - Campus Report",
        f"Overall academic and operations summary | generated {data['generated'].strftime('%d %B %Y')}",
    )
    report.heading('Campus at a glance')
    report.key_values([
        ('Students', f"{stats['total_students']:,}"),
        ('Departments', stats['total_departments']),
        ('Faculty (active)', stats['faculty_members']),
        ('Courses', stats['total_courses']),
        ('Course offerings', stats['total_offerings']),
        ('Enrollments', f"{stats['total_enrollments']:,}"),
        ('Attendance', f"{stats['attendance_pct']}%"),
        ('Recorded results', f"{stats['result_count']:,}"),
        ('Pending admissions', stats['pending_admissions']),
        ('Fees collected (INR)', f"{stats['total_collected']:,.2f}") if financial else ('Fee visibility', 'Administrator only'),
    ])
    report.heading('Students by department')
    report.table(
        ['Code', 'Department', 'Students', 'Active faculty'],
        [[row['dept_code'], row['dept_name'], row['students'], row['faculty']] for row in data['by_department']],
        widths=[1, 3, 1, 1], align_right=(2, 3),
    )
    report.heading('Students by status')
    report.table(['Status', 'Students'], [[row['status'], row['total']] for row in data['by_status']],
                 widths=[2, 1], align_right=(1,))
    report.heading('Result grades (all recorded exams)')
    report.table(['Grade', 'Results'], [[row['grade'] or 'Ungraded', row['total']] for row in data['grade_mix']],
                 widths=[2, 1], align_right=(1,))
    if financial:
        report.heading('Fee status (current semester)')
        report.table(
            ['Status', 'Students', 'Outstanding (INR)'],
            [[row['payment_status'], row['students'], f"{float(row['outstanding']):,.2f}"] for row in data['fee_status']],
            widths=[2, 1, 2], align_right=(1, 2),
        )
    if tables is not None:
        report.heading('Database tables (row counts)')
        report.table(['Table', 'Rows'], [[row['name'], f"{row['rows']:,}"] for row in tables],
                     widths=[3, 1], align_right=(1,))
    report.paragraph(
        'This report is generated from live database records. Blank departments and zero counts reflect '
        'the current data, not missing pages. Financial figures are shown to administrators only.'
    )
    return report.to_bytes()


def student_report(student, enrollments, results, fees, attendance):
    report = Report(
        f"{Config.PORTAL_NAME} - Student Report",
        f"{student['roll_no']} | {student['first_name']} {student['last_name']} | generated {date.today().strftime('%d %B %Y')}",
    )
    report.heading('Student details')
    report.key_values([
        ('Full name', f"{student['first_name']} {student['last_name']}"),
        ('Roll number', student['roll_no']),
        ('Department', f"{student['dept_code']} - {student['dept_name']}"),
        ('Semester', student['current_semester']),
        ('Status', student['status']),
        ('Admission date', student['admission_date']),
        ('Email', student['email']),
        ('Phone', student['phone']),
        ('Date of birth', student['dob']),
        ('CGPA', student.get('cgpa') if student.get('cgpa') is not None else 'Not graded yet'),
    ])
    report.heading('Enrolled courses')
    report.table(
        ['Course', 'Title', 'Credits', 'Term', 'Attendance %'],
        [[row['course_code'], row['course_title'], row['credits'], f"{row['academic_year']} {row['term']}",
          row['attendance_percentage']] for row in enrollments],
        widths=[1, 3, 1, 2, 1.3], align_right=(2, 4),
    )
    report.heading('Exam results')
    report.table(
        ['Course', 'Exam', 'Date', 'Marks', 'Max', 'Percent', 'Grade'],
        [[row['course_code'], row['exam_type'], row['exam_date'], row['marks_obtained'], row['max_marks'],
          row['percentage'], row['grade']] for row in results],
        widths=[1, 1.2, 1.5, 1, 1, 1.2, 1], align_right=(3, 4, 5, 6),
    )
    report.heading('Attendance summary')
    report.table(
        ['Course', 'Classes', 'Present', 'Late', 'Absent', 'Attendance %'],
        [[row['course_code'], row['total_classes'], row['present_count'], row['late_count'],
          row['absent_count'], row['attendance_percentage']] for row in attendance],
        widths=[1.2, 1, 1, 1, 1, 1.4], align_right=(1, 2, 3, 4, 5),
    )
    if fees:
        report.heading('Fee ledger')
        report.table(
            ['Semester', 'Fee due (INR)', 'Paid (INR)', 'Balance (INR)', 'Status'],
            [[row['semester_no'], f"{float(row['total_fee']):,.2f}", f"{float(row['total_paid']):,.2f}",
              f"{float(row['balance_due']):,.2f}", row['payment_status']] for row in fees],
            widths=[1, 1.6, 1.5, 1.5, 1.4], align_right=(1, 2, 3),
        )
    report.paragraph('Generated from recorded enrollments, exams, attendance, and payments. '
                     'Course completion and official transcripts are subject to university policy.')
    return report.to_bytes()
