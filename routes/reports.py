"""HTML reports and downloadable PDF summaries."""
import csv
import io
from flask import Blueprint, Response, abort, render_template, session
from routes.auth import login_required, role_required
from repositories import reports
from repositories.db_pool import db_pool
from repositories.students import StudentRepository

reports_bp = Blueprint('reports', __name__)


def _pdf(payload, filename):
    return Response(payload, mimetype='application/pdf', headers={
        'Content-Disposition': f'attachment; filename={filename}',
        'Cache-Control': 'no-store',
    })


@reports_bp.route('/reports')
@login_required
@role_required('admin', 'faculty')
def reports_view():
    is_admin = session.get('role') == 'admin'
    tables = reports.database_tables() if is_admin else None
    return render_template('reports/index.html', data=reports.overview(), is_admin=is_admin,
                           tables=tables, tables_total=sum(t['rows'] for t in tables or []))


@reports_bp.route('/reports/summary.pdf')
@login_required
@role_required('admin', 'faculty')
def summary_pdf():
    is_admin = session.get('role') == 'admin'
    tables = reports.database_tables() if is_admin else None
    return _pdf(reports.summary_report(financial=is_admin, tables=tables), 'nist-campus-report.pdf')


@reports_bp.route('/students/<int:student_id>/report.pdf')
@login_required
def student_pdf(student_id):
    role = session.get('role')
    if role not in ('admin', 'faculty', 'student'):
        abort(403)
    if role == 'student' and student_id != session.get('student_id'):
        abort(403, description='You can only download your own report.')
    student = StudentRepository.get_by_id(student_id)
    if not student:
        abort(404, description='Student not found.')
    if role == 'faculty':
        owns = StudentRepository.faculty_can_access(student_id, session.get('faculty_id'))
        if not owns:
            abort(403, description='This student is not enrolled in your course offerings.')
    fees = StudentRepository.get_fee_summary(student_id) if role in ('admin', 'student') else []
    payload = reports.student_report(
        student,
        StudentRepository.get_enrollments(student_id),
        StudentRepository.get_results(student_id),
        fees,
        StudentRepository.get_attendance_summary(student_id),
    )
    return _pdf(payload, f"nist-student-{student['roll_no']}.pdf")


def _safe_csv(value):
    text = '' if value is None else str(value)
    # Stop spreadsheet formula execution from database text fields.
    return "'" + text if text.lstrip().startswith(('=', '+', '-', '@', '\t', '\r')) else text


@reports_bp.route('/reports/tables/<table_name>.csv')
@login_required
@role_required('admin')
def table_csv(table_name):
    """Raw table export for administrators, without credential columns."""
    if table_name not in {table['name'] for table in reports.database_tables()}:
        abort(404, description='Unknown table.')
    rows = db_pool.execute_query(f'SELECT * FROM {table_name}')
    columns = [key for key in (rows[0].keys() if rows else []) if key not in ('password_hash', 'photo_url')]
    if not columns:
        # Empty table: read the schema to emit a header row.
        if db_pool.is_mysql:
            rows_schema = db_pool.execute_query(
                "SELECT column_name AS name FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name=%s",
                (table_name,), fetch='all')
            columns = [row['name'] for row in rows_schema if row['name'] not in ('password_hash', 'photo_url')]
        else:
            columns = [row['name'] for row in db_pool.execute_query(f'PRAGMA table_info({table_name})')
                       if row['name'] not in ('password_hash', 'photo_url')]
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(columns)
    for row in rows:
        writer.writerow([_safe_csv(row[column]) for column in columns])
    return Response(output.getvalue(), mimetype='text/csv', headers={
        'Content-Disposition': f'attachment; filename=nist-{table_name}.csv',
        'Cache-Control': 'no-store',
    })
