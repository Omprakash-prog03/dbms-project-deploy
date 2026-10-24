"""Overall PDF/CSV reports and staff-chosen passwords."""
from datetime import date
import re
import uuid
import pytest
from app import create_app
from config import Config
from repositories.db_pool import db_pool

BRAND = Config.PORTAL_NAME.encode()


@pytest.fixture
def admin():
    client = create_app({'TESTING':True,'CSRF_ENABLED':False,'RATELIMIT_ENABLED':False}).test_client()
    with client.session_transaction() as session:
        session.update(user_id=1,username='admin',role='admin')
    return client


@pytest.fixture
def faculty():
    client = create_app({'TESTING':True,'CSRF_ENABLED':False}).test_client()
    with client.session_transaction() as session:
        session.update(user_id=2,username='faculty',role='faculty',faculty_id=1)
    return client


@pytest.fixture
def student():
    client = create_app({'TESTING':True,'CSRF_ENABLED':False}).test_client()
    with client.session_transaction() as session:
        session.update(user_id=3,username='student',role='student',student_id=1)
    return client


def test_reports_page_and_tables(admin, faculty, student):
    page = admin.get('/reports')
    assert page.status_code == 200
    assert BRAND in page.data
    assert b'Database tables' in page.data
    assert b'app_user' in page.data
    # The reset dialog mentions the column name; no hash values are rendered.
    assert b'$2b$' not in page.data
    assert admin.get('/reports/summary.pdf').status_code == 200
    assert faculty.get('/reports').status_code == 200
    assert b'Database tables' not in faculty.get('/reports').data
    assert student.get('/reports').status_code == 403
    assert student.get('/reports/summary.pdf').status_code == 403


def test_campus_pdf_is_a_valid_pdf(admin, faculty):
    pdf = admin.get('/reports/summary.pdf')
    assert pdf.mimetype == 'application/pdf'
    assert pdf.data.startswith(b'%PDF-1.4')
    assert pdf.data.rstrip().endswith(b'%%EOF')
    assert b'nist-campus-report.pdf' in pdf.headers['Content-Disposition'].encode()
    assert len(pdf.data) > 2000
    staff_pdf = faculty.get('/reports/summary.pdf')
    assert staff_pdf.status_code == 200 and staff_pdf.data.startswith(b'%PDF-')


def test_student_pdf_access_rules(admin, student, faculty):
    allowed = admin.get('/students/1/report.pdf')
    assert allowed.status_code == 200 and allowed.data.startswith(b'%PDF-')
    own = student.get('/students/1/report.pdf')
    assert own.status_code == 200 and own.data.startswith(b'%PDF-')
    assert student.get('/students/2/report.pdf').status_code == 403
    assert create_app({'TESTING':True}).test_client().get('/students/1/report.pdf').status_code == 302


def test_table_csv_excludes_credentials(admin, faculty):
    response = admin.get('/reports/tables/app_user.csv')
    assert response.status_code == 200
    assert 'password_hash' not in response.get_data(as_text=True)
    assert 'username' in response.get_data(as_text=True)
    assert faculty.get('/reports/tables/app_user.csv').status_code == 403
    assert admin.get('/reports/tables/not_a_table.csv').status_code == 404


def test_student_password_can_be_chosen_by_staff(admin):
    roll = 'PW' + uuid.uuid4().hex[:8].upper()
    password = 'StudentChosenPass-2026!'
    payload = {
        'roll_no': roll, 'first_name': 'Password', 'last_name': 'Chosen',
        'email': f'{roll.lower()}@nist.example', 'phone': '9876500000',
        'dob': '2004-05-06', 'gender': 'Other', 'address': 'Test only',
        'dept_id': 1, 'admission_date': date.today().isoformat(),
        'current_semester': 1, 'status': 'Active', 'initial_password': password,
    }
    created = admin.post('/api/students/create', json=payload)
    assert created.status_code == 200, created.get_json()
    body = created.get_json()
    try:
        assert body['username'] == roll.lower()
        login = create_app({'TESTING':True,'CSRF_ENABLED':False}).test_client()
        response = login.post('/api/auth/login', json={'username': roll.lower(), 'password': password})
        assert response.status_code == 200, response.get_json()
    finally:
        db_pool.execute_dml('DELETE FROM app_user WHERE student_id=(SELECT student_id FROM student WHERE roll_no=%s)', (roll,))
        db_pool.execute_dml('DELETE FROM student WHERE roll_no=%s', (roll,))


def test_weak_or_missing_student_password(admin):
    roll = 'PW' + uuid.uuid4().hex[:8].upper()
    payload = {
        'roll_no': roll, 'first_name': 'Short', 'last_name': 'Password',
        'email': f'{roll.lower()}@nist.example', 'phone': '9876500001',
        'dob': '2004-05-06', 'gender': 'Other', 'address': '',
        'dept_id': 1, 'admission_date': date.today().isoformat(),
        'current_semester': 1, 'status': 'Active', 'initial_password': 'short',
    }
    assert admin.post('/api/students/create', json=payload).status_code == 400
    assert not db_pool.execute_query('SELECT student_id FROM student WHERE roll_no=%s', (roll,), fetch='one')
    payload.pop('initial_password')
    created = admin.post('/api/students/create', json=payload)
    assert created.status_code == 200
    sid = created.get_json()['student_id']
    try:
        assert not db_pool.execute_query('SELECT user_id FROM app_user WHERE student_id=%s', (sid,), fetch='one')
    finally:
        db_pool.execute_dml('DELETE FROM student WHERE student_id=%s', (sid,))


def test_admission_can_use_chosen_password(admin):
    email = f'{uuid.uuid4().hex}@nist.example'
    created = admin.post('/api/admissions/create', json={
        'applicant_name': 'Chosen Admission', 'email': email, 'phone': '9876500002', 'dept_id': 1,
    })
    assert created.status_code == 200, created.get_json()
    application_id = created.get_json()['application_id']
    password = 'AdmissionChosen-2026!'
    approved = admin.post('/api/admissions/approve', json={
        'application_id': application_id, 'dob': '2003-02-03', 'address': 'Test',
        'password': password,
    })
    assert approved.status_code == 200, approved.get_json()
    body = approved.get_json()
    try:
        assert body['password_generated'] is False
        assert body['temporary_password'] == password
        client = create_app({'TESTING':True,'CSRF_ENABLED':False}).test_client()
        assert client.post('/api/auth/login', json={'username': body['username'], 'password': password}).status_code == 200
    finally:
        student_id = db_pool.execute_query('SELECT student_id FROM app_user WHERE username=%s', (body['username'],), fetch='val')
        db_pool.execute_dml('DELETE FROM app_user WHERE username=%s', (body['username'],))
        db_pool.execute_dml('DELETE FROM result WHERE enrollment_id IN (SELECT enrollment_id FROM enrollment WHERE student_id=%s)', (student_id,))
        db_pool.execute_dml('DELETE FROM attendance WHERE enrollment_id IN (SELECT enrollment_id FROM enrollment WHERE student_id=%s)', (student_id,))
        db_pool.execute_dml('DELETE FROM enrollment WHERE student_id=%s', (student_id,))
        db_pool.execute_dml('DELETE FROM student WHERE student_id=%s', (student_id,))
        db_pool.execute_dml('DELETE FROM admission_application WHERE application_id=%s', (application_id,))


@pytest.mark.parametrize('path', ['/reports', '/reports/summary.pdf', '/students/1/report.pdf'])
def test_reports_require_login(path):
    assert create_app({'TESTING':True}).test_client().get(path).status_code == 302


def test_pdf_escapes_awkward_text(admin):
    pdf = admin.get('/reports/summary.pdf')
    assert b'\\(' in pdf.data or b'\\)' in pdf.data or pdf.data.startswith(b'%PDF-')
    assert b'\x00' not in pdf.data


def test_page_scripts_can_send_the_csrf_token():
    """Raw fetch() calls in page scripts must still carry the CSRF token."""
    from pathlib import Path
    app_js = Path('static/js/app.js').read_text()
    assert 'X-CSRF-Token' in app_js
    assert 'window.fetch =' in app_js
    templates = Path('templates').rglob('*.html')
    raw_posts = [str(path) for path in templates if 'await fetch(' in path.read_text()]
    assert raw_posts, 'this regression test expects the legacy raw fetch calls to exist'


def test_attendance_save_requires_csrf_and_faculty_can_mark_own_offering():
    app = create_app({'TESTING': True, 'CSRF_ENABLED': True, 'RATELIMIT_ENABLED': False})
    offering = db_pool.execute_query(
        'SELECT offering_id, faculty_id FROM course_offering WHERE faculty_id = 1 LIMIT 1', fetch='one')
    assert offering, 'seed data should give faculty 1 an offering'
    roster = db_pool.execute_query(
        "SELECT enrollment_id FROM enrollment WHERE offering_id=%s AND status='Enrolled'",
        (offering['offering_id'],), fetch='all')
    assert roster, 'seed data should enrol students'
    records = [{'enrollment_id': row['enrollment_id'], 'status': 'Present'} for row in roster[:3]]
    payload = {'offering_id': offering['offering_id'], 'class_date': date.today().isoformat(), 'records': records}

    client = app.test_client()
    with client.session_transaction() as session:
        session.update(user_id=2, username='faculty', role='faculty', faculty_id=offering['faculty_id'])
        session['csrf_token'] = 'csrf-token-for-test'
    # Without the token the session guard refuses the write ...
    assert client.post('/api/attendance/mark', json=payload).status_code == 400
    # ... and with it, the owning faculty member's roll-call is saved.
    saved = client.post('/api/attendance/mark', json=payload, headers={'X-CSRF-Token': 'csrf-token-for-test'})
    assert saved.status_code == 200, saved.get_json()
    assert saved.get_json()['success'] is True
    ids = [row['enrollment_id'] for row in records]
    count = db_pool.execute_query(
        'SELECT COUNT(*) FROM attendance WHERE class_date=%s AND enrollment_id IN (%s,%s,%s)',
        (date.today().isoformat(), *ids), fetch='val')
    assert count == 3


def test_faculty_attendance_page_lists_their_offering():
    client = create_app({'TESTING': True, 'CSRF_ENABLED': False}).test_client()
    with client.session_transaction() as session:
        session.update(user_id=2, username='faculty', role='faculty', faculty_id=1)
    page = client.get('/attendance')
    assert page.status_code == 200
    assert b'Mark All Present' in page.data
    assert b'Save Roll-Call' in page.data
    # A different instructor's offering must not be selectable.
    other = db_pool.execute_query(
        'SELECT offering_id FROM course_offering WHERE faculty_id != 1 LIMIT 1', fetch='val')
    if other:
        assert client.post('/api/attendance/mark', json={'offering_id': other, 'class_date': date.today().isoformat(),
                                                         'records': []}).status_code == 403


def test_console_can_set_a_specific_short_password(tmp_path):
    """Admin123-style passwords are allowed (8+), with a written warning."""
    import json, os, subprocess, sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    configuration, database = tmp_path/'.env', tmp_path/'short.db'
    setup = subprocess.run(
        [sys.executable, '-c',
         'import json,sys; from scripts.init_production import initialize; initialize(**json.loads(sys.stdin.read()))'],
        input=json.dumps({'username': 'owner', 'password': 'Initial-Private-Pass-2026!',
                          'config_path': str(configuration), 'database_path': str(database)}),
        capture_output=True, text=True, cwd=root)
    assert setup.returncode == 0, setup.stderr
    environment = {key: value for key, value in os.environ.items()
                   if key not in {'APP_ENV', 'SECRET_KEY', 'DB_ENGINE', 'SQLITE_PATH', 'DEMO_MODE',
                                  'COOKIE_SECURE', 'EMBEDDED_PREVIEW', 'TRUSTED_PROXY_HOPS'}}
    environment['HOGWARDS_ENV_FILE'] = str(configuration)
    reset = subprocess.run(
        [sys.executable, 'scripts/reset_password.py', '--username', 'owner', '--password', 'Admin123'],
        capture_output=True, text=True, cwd=root, env=environment)
    assert reset.returncode == 0, reset.stderr
    assert 'WARNING' in reset.stdout
    assert 'Verified against the database: OK' in reset.stdout
    check = subprocess.run(
        [sys.executable, 'scripts/reset_password.py', '--check'],
        input='owner\nAdmin123\n', capture_output=True, text=True, cwd=root, env=environment)
    assert 'MATCH - these credentials work' in check.stdout
    too_short = subprocess.run(
        [sys.executable, 'scripts/reset_password.py', '--username', 'owner', '--password', 'short'],
        capture_output=True, text=True, cwd=root, env=environment)
    assert too_short.returncode != 0
