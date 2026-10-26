"""The change log: what administrators and faculty changed, detected automatically."""
import bcrypt
import pytest

from app import create_app
from config import Config
from repositories import admin_sessions, login_history, owner, staff_activity
from repositories.db_pool import db_pool


@pytest.fixture(autouse=True)
def fresh_log(monkeypatch):
    from repositories.owner import GUARD_TABLE, REQUEST_TABLE
    owner.ensure_schema()
    admin_sessions.ensure_schema()
    db_pool.execute_dml(f'DELETE FROM {owner.GUARD_TABLE}')
    db_pool.execute_dml(f'DELETE FROM {owner.REQUEST_TABLE}')
    db_pool.execute_dml(f'DELETE FROM {admin_sessions.TABLE}')
    db_pool.execute_dml("DELETE FROM app_user WHERE username IN ('om-2026', 'log-admin')")
    for trigger in ('trg_staff_activity_no_update', 'trg_staff_activity_no_delete'):
        db_pool.execute_dml(f'DROP TRIGGER IF EXISTS {trigger}')
    db_pool.execute_dml(f'DROP TABLE IF EXISTS {staff_activity.TABLE}')
    monkeypatch.setattr(staff_activity, '_ready', False)
    staff_activity.ensure_schema()
    yield
    # Leave the shared test database exactly as the rest of the suite expects it:
    # no master key (so the guard is open), no sessions, and no stray accounts.
    for account in ('om-2026', 'log-admin'):
        db_pool.execute_dml('DELETE FROM app_user WHERE username = %s', (account,))
        db_pool.execute_dml('DELETE FROM admin_session WHERE username = %s', (account,))
    for account in ('om-2026', 'log-admin'):
        db_pool.execute_dml('DELETE FROM app_user WHERE username = %s', (account,))
        db_pool.execute_dml('DELETE FROM admin_session WHERE username = %s', (account,))
    db_pool.execute_dml(f'DELETE FROM {GUARD_TABLE}')
    db_pool.execute_dml(f'DELETE FROM {REQUEST_TABLE}')
    staff_activity._ready = False
    login_history._ready = False


@pytest.fixture
def app():
    return create_app({'TESTING': True, 'CSRF_ENABLED': False, 'RATELIMIT_ENABLED': False})


def make_admin(username, password='log-admin-pass-1'):
    db_pool.execute_dml("DELETE FROM app_user WHERE username = %s", (username,))
    digest = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    db_pool.execute_dml(
        "INSERT INTO app_user (username, password_hash, role) VALUES (%s, %s, 'admin')",
        (username, digest))
    return db_pool.execute_query('SELECT user_id FROM app_user WHERE username = %s',
                                 (username,), fetch='val')


def admin_client(app, username='log-admin'):
    client = app.test_client()
    with client.session_transaction() as session:
        session.update(user_id=99, username=username, role='admin', access_approved=True,
                       owner_epoch=owner.epoch(),
                       admin_token_version=admin_sessions.version(username))
    return client


def faculty_client(app):
    client = app.test_client()
    with client.session_transaction() as session:
        session.update(user_id=2, username='faculty', role='faculty', faculty_id=1)
    return client


def entries():
    return staff_activity.recent(limit=200)


# ---------------------------------------------------------------------------
# automatic detection
# ---------------------------------------------------------------------------
def test_an_administrator_change_is_recorded_with_name_and_table(app, monkeypatch):
    monkeypatch.setattr(Config, 'OTP_EXEMPT_ADMINS', 'log-admin')
    make_admin('log-admin')
    client = admin_client(app, 'log-admin')
    response = client.post('/api/departments/create', json={
        'dept_code': 'LOG1', 'dept_name': 'Logged Department', 'established_year': 2020})
    assert response.status_code == 200, response.get_json()

    row = entries()[0]
    assert row['username'] == 'log-admin'
    assert row['role'] == 'admin'
    assert row['action'] == 'INSERT'
    assert row['object'] == 'department'
    assert 'dept_name=Logged Department' in row['detail']
    assert row['path'] == '/api/departments/create'
    assert row['at']


def test_a_faculty_change_is_recorded_too(app):
    client = faculty_client(app)
    offering = db_pool.execute_query(
        "SELECT o.offering_id FROM course_offering o JOIN faculty f "
        "ON f.faculty_id = o.faculty_id WHERE f.status = 'Active' LIMIT 1", fetch='val')
    if not offering:
        pytest.skip('no offering for a faculty member')
    enrollment = db_pool.execute_query(
        "SELECT e.enrollment_id FROM enrollment e JOIN student s ON s.student_id = e.student_id "
        "WHERE e.offering_id = %s AND e.status = 'Enrolled' AND s.status = 'Active' LIMIT 1",
        (offering,), fetch='one')
    if not enrollment:
        pytest.skip('no active enrollment in that offering')
    response = client.post('/api/attendance/mark', json={
        'offering_id': offering, 'class_date': '2026-02-02',
        'records': [{'enrollment_id': enrollment['enrollment_id'], 'status': 'Present'}]})
    assert response.status_code == 200, response.get_json()
    rows = [row for row in entries() if row['role'] == 'faculty']
    assert rows, 'a faculty write should be recorded'
    assert rows[0]['username'] == 'faculty'
    assert rows[0]['object'] == 'attendance'


def test_a_student_reading_is_never_recorded(app):
    student = app.test_client()
    with student.session_transaction() as session:
        session.update(user_id=3, username='student', role='student', student_id=1)
    student.get('/students/1')
    assert [row for row in entries() if row['role'] == 'student'] == []


def test_internal_tables_are_not_logged(app):
    make_admin('om-2026', 'Superadmin123')
    mine = app.test_client()
    with mine.session_transaction() as session:
        session.update(user_id=99, username='om-2026', role='admin', access_approved=True,
                       supreme=True, owner_epoch=owner.epoch(),
                       admin_token_version=admin_sessions.version('om-2026'))
    mine.post('/owner/sign-out/log-admin')
    assert all(row['object'] not in staff_activity.LOCKED_TABLES for row in entries())


def test_the_sql_console_write_is_recorded(app):
    make_admin('log-admin')
    client = admin_client(app, 'log-admin')
    client.post('/raw-data/query', data={'statement':
               "UPDATE department SET dept_name = dept_name WHERE dept_code = 'CSE'"})
    row = entries()[0]
    assert row['action'] == 'UPDATE'
    assert row['object'] == 'department'
    assert row['username'] == 'log-admin'
    assert 'dept_name = dept_name' in row['detail']


def test_a_refused_or_read_only_statement_is_not_a_change(app):
    make_admin('log-admin')
    client = admin_client(app, 'log-admin')
    for statement in ("DELETE FROM login_history", "SELECT * FROM department",
                      "UPDATE department SET dept_name = 'x' WHERE 1"):
        client.post('/raw-data/query', data={'statement': statement})
    assert entries() == [], 'reads and refused statements are not changes'


# ---------------------------------------------------------------------------
# it cannot be altered
# ---------------------------------------------------------------------------
def test_the_database_refuses_to_change_the_log():
    db_pool.execute_dml(
        f"INSERT INTO {staff_activity.TABLE} (username, role, action, object, detail, path, "
        "happened_at, address) VALUES ('log-admin', 'admin', 'UPDATE', 'student', 'seed', "
        "'/students/1/edit', '2026-01-01 00:00:00', '')")
    with pytest.raises(Exception):
        db_pool.execute_dml(f"UPDATE {staff_activity.TABLE} SET username = 'someone'")
    with pytest.raises(Exception):
        db_pool.execute_dml(f"DELETE FROM {staff_activity.TABLE}")


def test_the_sql_console_refuses_to_write_the_log():
    from repositories import sqlconsole
    for statement in (
        f"DELETE FROM {staff_activity.TABLE}",
        f"UPDATE {staff_activity.TABLE} SET rows_changed = 0",
        f"INSERT INTO {staff_activity.TABLE} (username, role, verb, object, happened_at) "
        "VALUES ('x','admin','INSERT','student','2026-01-01 00:00:00')",
    ):
        outcome = sqlconsole.run(statement, allow_full_write=True)
        assert outcome['ok'] is False, statement
        assert 'append-only' in outcome['error']


# ---------------------------------------------------------------------------
# the section and its downloads
# ---------------------------------------------------------------------------
def test_the_dashboard_lists_the_changes_per_username(app):
    make_admin('om-2026', 'Superadmin123')
    for username, verb in (('log-admin', 'UPDATE'), ('log-admin', 'INSERT'),
                           ('faculty', 'UPDATE')):
        db_pool.execute_dml(
            f"INSERT INTO {staff_activity.TABLE} (username, role, action, object, detail, path, "
            "happened_at, address) VALUES (%s, %s, %s, 'student', 'seeded change', "
            "'/students/1/edit', '2026-01-01 00:00:00', '10.0.0.5')",
            (username, 'admin' if username != 'faculty' else 'faculty', verb))
    mine = app.test_client()
    with mine.session_transaction() as session:
        session.update(user_id=99, username='om-2026', role='admin', access_approved=True,
                       supreme=True, owner_epoch=owner.epoch(),
                       admin_token_version=admin_sessions.version('om-2026'))
    body = mine.get('/owner').get_data(as_text=True)
    assert 'Change log' in body
    assert 'log-admin' in body
    assert 'student' in body
    assert 'CSV' in body and 'PDF' in body
    section = body[body.index('id="change-log"'):body.index('Owner activity')]
    assert 'log-admin' in section and 'faculty' in section


def test_the_downloads_are_csv_and_pdf(app):
    make_admin('om-2026', 'Superadmin123')
    db_pool.execute_dml(
        f"INSERT INTO {staff_activity.TABLE} (username, role, action, object, detail, path, "
        "happened_at, address) VALUES ('log-admin', 'admin', 'DELETE', 'fee_payment', "
        "'receipt=42', '/fees/42/delete', '2026-01-01 00:00:00', '10.0.0.5')")
    mine = app.test_client()
    with mine.session_transaction() as session:
        session.update(user_id=99, username='om-2026', role='admin', access_approved=True,
                       supreme=True, owner_epoch=owner.epoch(),
                       admin_token_version=admin_sessions.version('om-2026'))

    sheet = mine.get('/owner/activity.csv')
    assert sheet.status_code == 200
    assert 'nist_change_log.csv' in sheet.headers['Content-Disposition']
    assert 'log-admin' in sheet.get_data(as_text=True)

    document = mine.get('/owner/activity.pdf')
    assert document.status_code == 200
    assert document.data.startswith(b'%PDF-')

    history = mine.get('/owner/history.pdf')
    assert history.status_code == 200
    assert history.data.startswith(b'%PDF-')
    history_csv = mine.get('/owner/history.csv')
    assert 'nist_sign_in_history.csv' in history_csv.headers['Content-Disposition']


def test_only_the_supreme_administrator_can_download(app):
    make_admin('om-2026', 'Superadmin123')
    make_admin('log-admin')
    assert admin_client(app, 'log-admin').get('/owner/activity.csv').status_code == 403
    assert app.test_client().get('/owner/activity.csv').status_code == 302
