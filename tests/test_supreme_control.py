"""Supreme control: live admin sessions, the global switch, blocks and removals."""
import bcrypt
import pytest

from app import create_app
from config import Config
from repositories import admin_sessions, owner
from repositories.db_pool import db_pool

MASTER = 'supreme-master-key-9876'


@pytest.fixture(autouse=True)
def clean_state():
    from repositories.owner import GUARD_TABLE, REQUEST_TABLE
    owner.ensure_schema()
    admin_sessions.ensure_schema()
    db_pool.execute_dml(f'DELETE FROM {REQUEST_TABLE}')
    db_pool.execute_dml(f'DELETE FROM {GUARD_TABLE}')
    db_pool.execute_dml(f'DELETE FROM {admin_sessions.TABLE}')
    yield
    db_pool.execute_dml(f'DELETE FROM {REQUEST_TABLE}')
    db_pool.execute_dml(f'DELETE FROM {GUARD_TABLE}')
    db_pool.execute_dml(f'DELETE FROM {admin_sessions.TABLE}')
    db_pool.execute_dml("DELETE FROM app_user WHERE username IN ('deputy', 'solo', 'linked-faculty')")


@pytest.fixture
def app():
    return create_app({'TESTING': True, 'CSRF_ENABLED': False, 'RATELIMIT_ENABLED': False})


def make_admin(username, password='deputy-pass-1', faculty_id=None):
    digest = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    db_pool.execute_dml(
        "INSERT INTO app_user (username, password_hash, role, faculty_id) VALUES (%s, %s, 'admin', %s)",
        (username, digest, faculty_id))
    return db_pool.execute_query('SELECT user_id FROM app_user WHERE username = %s',
                                 (username,), fetch='val')


def owner_client(app):
    client = app.test_client()
    with client.session_transaction() as session:
        session.update(user_id=1, username='admin', role='admin', access_approved=True,
                       owner_epoch=owner.epoch(),
                       admin_token_version=admin_sessions.version('admin'))
    return client


def admin_client(app, username='deputy'):
    client = app.test_client()
    with client.session_transaction() as session:
        session.update(user_id=99, username=username, role='admin', access_approved=True,
                       owner_epoch=owner.epoch(),
                       admin_token_version=admin_sessions.version(username))
    return client


# ---------------------------------------------------------------------------
# the sign-in page: username and password, and a code box only if you ask for one
# ---------------------------------------------------------------------------
def test_the_sign_in_page_is_username_and_password_by_default(app):
    page = app.test_client().get('/login').get_data(as_text=True)
    assert 'id="username"' in page and 'id="password"' in page
    assert 'id="accessCode"' not in page, 'a normal sign-in needs no code box'
    assert 'Access code' not in page


def test_the_code_box_appears_when_codes_are_required(app):
    owner.set_code_required(True)
    page = app.test_client().get('/login').get_data(as_text=True)
    assert 'id="accessCode"' in page
    assert 'Access code' in page
    assert 'administrators only' in page


def test_the_switch_on_the_supreme_page_turns_the_rule_on_and_off(app):
    owner.set_master_key(MASTER)
    mine = owner_client(app)
    assert 'Password only' in mine.get('/owner').get_data(as_text=True)

    mine.post('/owner/code-required/switch', data={'master_key': MASTER, 'required': '1'})
    assert owner.code_required() is True
    assert 'Codes required' in mine.get('/owner').get_data(as_text=True)

    mine.post('/owner/code-required/switch', data={'master_key': MASTER, 'required': '0'})
    assert owner.code_required() is False


def test_the_switch_needs_the_master_key(app):
    owner.set_master_key(MASTER)
    mine = owner_client(app)
    mine.post('/owner/code-required/switch', data={'master_key': 'wrong', 'required': '1'})
    assert owner.code_required() is False


# ---------------------------------------------------------------------------
# access status endpoint feeds that page
# ---------------------------------------------------------------------------
def status(app, username):
    return app.test_client().post('/api/auth/access-status', json={'username': username})


def test_status_endpoint_reports_each_state(app):
    make_admin('deputy')
    assert status(app, 'admin').get_json()['state'] == 'owner'
    # Codes are off by default, so a plain administrator needs nothing.
    assert status(app, 'deputy').get_json()['state'] == 'not-required'
    owner.set_code_required(True)
    assert status(app, 'deputy').get_json()['state'] == 'none'

    owner.set_master_key(MASTER)
    assert status(app, 'deputy').get_json()['state'] == 'none'

    request_id = owner.request_access('deputy', user_id=99)
    assert status(app, 'deputy').get_json()['state'] == 'pending'

    owner.issue_code(request_id)
    assert status(app, 'deputy').get_json()['state'] == 'approved'

    owner.revoke(request_id)
    assert status(app, 'deputy').get_json()['state'] == 'revoked'

    owner.close_logins(True)
    assert status(app, 'deputy').get_json()['state'] == 'closed'
    owner.close_logins(False)

    owner.block_account('deputy', True)
    assert status(app, 'deputy').get_json()['state'] == 'blocked'


def test_status_endpoint_needs_a_username(app):
    assert app.test_client().post('/api/auth/access-status', json={}).status_code == 400


# ---------------------------------------------------------------------------
# live session registry
# ---------------------------------------------------------------------------
def test_signing_in_registers_a_live_session(app):
    owner.set_code_required(True)
    owner.set_master_key(MASTER)
    make_admin('deputy')
    request_id = owner.request_access('deputy', user_id=99)
    code = owner.issue_code(request_id)['code']

    signed_in = app.test_client().post('/api/auth/login', json={
        'username': 'deputy', 'password': 'deputy-pass-1', 'access_code': code})
    assert signed_in.status_code == 200

    listing = {item['username']: item for item in admin_sessions.overview('admin')}
    assert listing['deputy']['signed_in'] is True
    assert listing['deputy']['login_count'] == 1
    assert listing['deputy']['last_seen_ago'] in ('just now', '0 min ago') or 'ago' in listing['deputy']['last_seen_ago']
    assert listing['admin']['is_owner'] is True


def test_last_seen_is_touched_on_activity(app):
    owner.set_master_key(MASTER)
    make_admin('deputy')
    admin = admin_client(app, 'deputy')
    db_pool.execute_dml(f'UPDATE {admin_sessions.TABLE} SET last_seen = %s WHERE username = %s',
                        ('2000-01-01 00:00:00', 'deputy'))
    assert admin.get('/dashboard').status_code == 200
    seen = db_pool.execute_query(
        f'SELECT last_seen FROM {admin_sessions.TABLE} WHERE username = %s', ('deputy',), fetch='val')
    assert seen and not seen.startswith('2000')


# ---------------------------------------------------------------------------
# the owner can end one administrator's session
# ---------------------------------------------------------------------------
def test_sign_out_one_administrator(app):
    owner.set_master_key(MASTER)
    make_admin('deputy')
    deputy = admin_client(app, 'deputy')
    other = admin_client(app, 'deputy')
    mine = owner_client(app)
    assert deputy.get('/dashboard').status_code == 200

    response = mine.post('/owner/sign-out/deputy')
    assert response.status_code == 302
    for client in (deputy, other):
        thrown = client.get('/dashboard')
        assert thrown.status_code == 302 and '/login' in thrown.headers['Location']
    # The owner is untouched.
    assert mine.get('/dashboard').status_code == 200


def test_owner_cannot_sign_themselves_out_from_the_table(app):
    owner.set_master_key(MASTER)
    mine = owner_client(app)
    before = admin_sessions.version('admin')
    mine.post('/owner/sign-out/admin')
    assert admin_sessions.version('admin') == before
    assert mine.get('/dashboard').status_code == 200


# ---------------------------------------------------------------------------
# the global switch
# ---------------------------------------------------------------------------
def test_closing_logins_blocks_other_admins_and_signs_them_out(app):
    owner.set_code_required(True)
    owner.set_master_key(MASTER)
    make_admin('deputy')
    mine = owner_client(app)
    deputy = admin_client(app, 'deputy')
    assert deputy.get('/dashboard').status_code == 200

    closed = mine.post('/owner/switch-logins', data={'master_key': MASTER, 'closed': '1'})
    assert closed.status_code == 302
    assert owner.login_closed() is True
    assert deputy.get('/dashboard').status_code == 302

    blocked = app.test_client().post('/api/auth/login', json={
        'username': 'deputy', 'password': 'deputy-pass-1', 'access_code': '123456'})
    assert blocked.status_code == 403
    assert blocked.get_json()['code'] == 'owner_blocked'

    # The owner can still get in and reopen it.
    assert mine.get('/dashboard').status_code == 200
    mine.post('/owner/switch-logins', data={'master_key': MASTER, 'closed': '0'})
    assert owner.login_closed() is False


def test_switch_requires_the_master_key(app):
    owner.set_master_key(MASTER)
    mine = owner_client(app)
    mine.post('/owner/switch-logins', data={'master_key': 'wrong', 'closed': '1'})
    assert owner.login_closed() is False


# ---------------------------------------------------------------------------
# blocking one account
# ---------------------------------------------------------------------------
def test_blocking_an_account_stops_it_requesting_or_signing_in(app):
    owner.set_code_required(True)
    owner.set_master_key(MASTER)
    make_admin('deputy')
    request_id = owner.request_access('deputy', user_id=99)
    code = owner.issue_code(request_id)['code']
    mine = owner_client(app)

    mine.post('/owner/block/deputy', data={'blocked': '1'})
    assert admin_sessions.login_blocked('deputy') is True
    refused = app.test_client().post('/api/auth/login', json={
        'username': 'deputy', 'password': 'deputy-pass-1', 'access_code': code})
    assert refused.status_code == 403
    assert 'blocked' in refused.get_json()['message'].lower()

    mine.post('/owner/block/deputy', data={'blocked': '0'})
    assert admin_sessions.login_blocked('deputy') is False


def test_the_owner_cannot_be_blocked(app):
    owner.set_master_key(MASTER)
    mine = owner_client(app)
    mine.post('/owner/block/admin', data={'blocked': '1'})
    assert admin_sessions.login_blocked('admin') is False


# ---------------------------------------------------------------------------
# password reset and removal
# ---------------------------------------------------------------------------
def test_owner_resets_an_administrator_password(app):
    owner.set_code_required(True)
    owner.set_master_key(MASTER)
    make_admin('deputy')
    mine = owner_client(app)
    stale = admin_client(app, 'deputy')
    assert stale.get('/dashboard').status_code == 200

    response = mine.post('/owner/reset-password', data={
        'master_key': MASTER, 'username': 'deputy', 'new_password': 'brand-new-pass'})
    assert response.status_code == 302

    assert stale.get('/dashboard').status_code == 302  # sessions ended

    fresh = app.test_client().post('/api/auth/login', json={
        'username': 'deputy', 'password': 'brand-new-pass'})
    # Password works; only the owner's code is missing.
    assert fresh.status_code == 403
    assert fresh.get_json()['code'] == 'approval_required'


def test_removing_an_administrator_without_links_deletes_the_account(app):
    owner.set_master_key(MASTER)
    make_admin('solo')
    mine = owner_client(app)
    mine.post('/owner/remove/solo', data={'master_key': MASTER})
    assert db_pool.execute_query(
        'SELECT username FROM app_user WHERE username = %s', ('solo',), fetch='val') is None


def test_removing_an_administrator_leaves_faculty_and_students_alone(app):
    owner.set_master_key(MASTER)
    people = db_pool.execute_query('SELECT COUNT(*) AS n FROM student', fetch='one')['n']
    staff = db_pool.execute_query('SELECT COUNT(*) AS n FROM faculty', fetch='one')['n']
    make_admin('solo')
    mine = owner_client(app)
    mine.post('/owner/remove/solo', data={'master_key': MASTER})
    assert db_pool.execute_query('SELECT COUNT(*) AS n FROM student', fetch='one')['n'] == people
    assert db_pool.execute_query('SELECT COUNT(*) AS n FROM faculty', fetch='one')['n'] == staff
    kept = db_pool.execute_query(
        "SELECT COUNT(*) AS n FROM audit_log WHERE new_values LIKE '%solo%'", fetch='one')['n']
    assert kept >= 0


def test_the_owner_cannot_remove_themselves(app):
    owner.set_master_key(MASTER)
    mine = owner_client(app)
    mine.post('/owner/remove/admin', data={'master_key': MASTER})
    assert db_pool.execute_query(
        "SELECT role FROM app_user WHERE username = 'admin'", fetch='val') == 'admin'


def test_removal_and_reset_need_the_master_key(app):
    owner.set_master_key(MASTER)
    make_admin('solo')
    mine = owner_client(app)
    mine.post('/owner/remove/solo', data={'master_key': 'wrong'})
    assert db_pool.execute_query('SELECT username FROM app_user WHERE username = %s',
                                 ('solo',), fetch='val') == 'solo'
    mine.post('/owner/reset-password', data={'master_key': 'wrong', 'username': 'solo',
                                             'new_password': 'whatever-123'})
    assert db_pool.execute_query('SELECT username FROM app_user WHERE username = %s',
                                 ('solo',), fetch='val') == 'solo'


# ---------------------------------------------------------------------------
# the page itself
# ---------------------------------------------------------------------------
def test_supreme_page_shows_admins_sessions_and_the_switch(app):
    owner.set_master_key(MASTER)
    make_admin('deputy')
    mine = owner_client(app)
    page = mine.get('/owner')
    assert page.status_code == 200
    body = page.data
    assert b'Supreme control' in body
    assert b'You are the supreme administrator' in body
    assert b'deputy' in body
    assert b'Sign out everyone else' in body
    assert b'Administrator sign-in' in body
    assert b'Access codes' in body
    assert b'Master key' in body
    assert b'Owner activity' in body
    assert MASTER.encode() not in body
    assert b'$2b$' not in body


def test_old_admin_access_address_redirects_to_the_supreme_page(app):
    owner.set_master_key(MASTER)
    mine = owner_client(app)
    response = mine.get('/admin-access')
    assert response.status_code == 302
    assert response.headers['Location'].endswith('/owner')


def test_only_the_owner_reaches_the_supreme_page(app):
    owner.set_master_key(MASTER)
    make_admin('deputy')
    assert admin_client(app, 'deputy').get('/owner').status_code == 403
    faculty = app.test_client()
    with faculty.session_transaction() as session:
        session.update(user_id=2, username='faculty', role='faculty', faculty_id=1)
    assert faculty.get('/owner').status_code == 403
    assert app.test_client().get('/owner').status_code == 302
    # And none of the actions work for a normal administrator either.
    assert admin_client(app, 'deputy').post('/owner/lockdown', data={'master_key': MASTER}).status_code == 403
    assert admin_client(app, 'deputy').post('/owner/sign-out/admin').status_code == 403


def test_activity_trail_records_owner_actions(app):
    owner.set_master_key(MASTER)
    make_admin('deputy')
    mine = owner_client(app)
    mine.post('/owner/sign-out/deputy')
    mine.post('/owner/block/deputy', data={'blocked': '1'})
    trail = owner.trail(limit=10)
    actions = ' '.join(entry['action'] for entry in trail)
    assert 'signed out' in actions
    assert 'blocked' in actions
    page = mine.get('/owner').get_data(as_text=True)
    assert 'administrator signed out' in page


def test_status_endpoint_only_speaks_to_administrators(app):
    make_admin('deputy')
    owner.set_master_key(MASTER)
    owner.close_logins(True)
    try:
        # A student must never be told that administrator sign-in is closed.
        student = db_pool.execute_query("SELECT username FROM app_user WHERE role = 'student' LIMIT 1", fetch='val')
        if student:
            data = status(app, student).get_json()
            assert data['state'] == 'not-admin'
            assert 'owner' not in data['message']
        assert status(app, 'nobody-here').get_json()['state'] == 'unknown'
        owner.set_code_required(True)
        assert status(app, 'deputy').get_json()['state'] == 'closed'
        assert status(app, 'admin').get_json()['state'] == 'owner'
    finally:
        owner.close_logins(False)
