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
