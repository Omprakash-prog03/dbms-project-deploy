"""Owner controls: master key, one-tap lockdown, and administrator access codes."""
import pytest

from app import create_app
from config import Config
from repositories import owner
from repositories.db_pool import db_pool

MASTER = 'test-master-key-1234'


@pytest.fixture(autouse=True)
def clean_state():
    """Each test starts without a master key, a fresh epoch and no requests."""
    from repositories.owner import GUARD_TABLE, REQUEST_TABLE
    owner.ensure_schema()
    db_pool.execute_dml(f'DELETE FROM {REQUEST_TABLE}')
    db_pool.execute_dml(f'DELETE FROM {GUARD_TABLE}')
    yield
    db_pool.execute_dml(f'DELETE FROM {REQUEST_TABLE}')
    db_pool.execute_dml(f'DELETE FROM {GUARD_TABLE}')


@pytest.fixture
def app():
    return create_app({'TESTING': True, 'CSRF_ENABLED': False, 'RATELIMIT_ENABLED': False})


def client_for(app, username, role='admin', **extra):
    client = app.test_client()
    with client.session_transaction() as session:
        session.update(user_id=extra.pop('user_id', 1), username=username, role=role, **extra)
    return client


def second_admin_client(app, username='deputy'):
    """An approved, signed-in administrator who is not the owner."""
    client = app.test_client()
    with client.session_transaction() as session:
        session.update(user_id=99, username=username, role='admin', access_approved=True,
                       owner_epoch=owner.epoch())
    return client


# ---------------------------------------------------------------------------
# who is the owner
# ---------------------------------------------------------------------------
def test_first_administrator_is_the_owner():
    assert owner.owner_username() == 'admin'
    assert owner.is_owner('admin') is True
    assert owner.is_owner('ADMIN') is True          # case-insensitive
    assert owner.is_owner('deputy') is False
    assert owner.is_owner('') is False


def test_owner_can_be_configured_explicitly(monkeypatch):
    monkeypatch.setattr(Config, 'OWNER_USERNAME', 'omprakash')
    assert owner.owner_username() == 'omprakash'
    assert owner.is_owner('admin') is False


# ---------------------------------------------------------------------------
# master key
# ---------------------------------------------------------------------------
def test_master_key_is_hashed_and_verified():
    assert not owner.master_key_set()
    owner.set_master_key(MASTER)
    assert owner.master_key_set()
    assert owner.verify_master_key(MASTER)
    assert not owner.verify_master_key('wrong-key-0000')
    assert not owner.verify_master_key('')

    stored = db_pool.execute_query(
        "SELECT guard_value FROM owner_guard WHERE guard_key = 'master_key_hash'", fetch='val')
    assert stored and stored != MASTER
    assert stored.startswith('$2')

    # The masked hint never reveals the whole key.
    hint = owner.master_key_hint()
    assert MASTER not in hint and hint.startswith(MASTER[:4])


def test_master_key_has_a_minimum_length():
    with pytest.raises(ValueError):
        owner.set_master_key('short')


def test_generated_keys_are_unique_and_long_enough():
    keys = {owner.generate_master_key() for _ in range(25)}
    assert len(keys) == 25
    assert all(len(key) >= owner.MIN_MASTER_KEY for key in keys)


# ---------------------------------------------------------------------------
# access codes
# ---------------------------------------------------------------------------
def test_access_code_flow():
    owner.set_master_key(MASTER)
    request_id = owner.request_access('deputy', user_id=99)
    assert request_id
    assert [item['username'] for item in owner.pending_requests()] == ['deputy']

    issued = owner.issue_code(request_id)
    code = issued['code']
    assert len(code) == 6 and code.isdigit()

    # Wrong code is refused and counted.
    ok, message = owner.redeem_code('deputy', '000000')
    assert ok is False and 'not correct' in message
    ok, _ = owner.redeem_code('deputy', code)
    assert ok is True

    # Single use.
    ok, message = owner.redeem_code('deputy', code)
    assert ok is False


def test_code_expires():
    owner.set_master_key(MASTER)
    request_id = owner.request_access('deputy', user_id=99)
    owner.issue_code(request_id)
    db_pool.execute_dml(
        "UPDATE admin_access_request SET code_expires = '2000-01-01 00:00:00' WHERE request_id = %s",
        (request_id,))
    ok, message = owner.redeem_code('deputy', '123456')
    assert ok is False and 'expired' in message


def test_code_is_locked_after_five_wrong_attempts():
    owner.set_master_key(MASTER)
    request_id = owner.request_access('deputy', user_id=99)
    issued = owner.issue_code(request_id)
    for _ in range(5):
        owner.redeem_code('deputy', '999999')
    ok, message = owner.redeem_code('deputy', issued['code'])
    assert ok is False
    assert 'Too many' in message or 'no approved' in message


def test_request_without_an_approved_code_is_refused():
    owner.set_master_key(MASTER)
    ok, message = owner.redeem_code('deputy', '123456')
    assert ok is False and 'no approved access request' in message


def test_duplicate_requests_do_not_pile_up():
    owner.set_master_key(MASTER)
    first = owner.request_access('deputy', user_id=99)
    second = owner.request_access('deputy', user_id=99)
    assert first == second
    assert len(owner.pending_requests()) == 1


def test_revoked_request_disappears():
    owner.set_master_key(MASTER)
    request_id = owner.request_access('deputy', user_id=99)
    owner.revoke(request_id)
    assert owner.pending_requests() == []


# ---------------------------------------------------------------------------
# login gate
# ---------------------------------------------------------------------------
def test_owner_logs_in_without_a_code(app):
    owner.set_master_key(MASTER)
    response = app.test_client().post('/api/auth/login', json={'username': 'admin', 'password': 'admin123'})
    assert response.status_code == 200, response.get_json()
    assert response.get_json()['success'] is True


def test_other_administrator_is_blocked_until_a_code_is_issued(app):
    owner.set_master_key(MASTER)
    # A second admin account, created the same way the portal creates one.
    import bcrypt
    digest = bcrypt.hashpw(b'deputy-pass-1', bcrypt.gensalt()).decode()
    db_pool.execute_dml(
        "INSERT INTO app_user (username, password_hash, role) VALUES (%s, %s, 'admin')",
        ('deputy', digest))
    user_id = db_pool.execute_query("SELECT user_id FROM app_user WHERE username = 'deputy'", fetch='val')
    try:
        client = app.test_client()
        blocked = client.post('/api/auth/login', json={'username': 'deputy', 'password': 'deputy-pass-1'})
        assert blocked.status_code == 403
        payload = blocked.get_json()
        assert payload['code'] == 'approval_required'
        assert 'owner' in payload['message'].lower()

        # The owner sees the request and issues a code.
        pending = owner.pending_requests()
        assert [item['username'] for item in pending] == ['deputy']
        code = owner.issue_code(pending[0]['request_id'])['code']

        # Still refused with a bad code, accepted with the real one.
        wrong = app.test_client().post('/api/auth/login', json={
            'username': 'deputy', 'password': 'deputy-pass-1', 'access_code': '000000'})
        assert wrong.status_code == 403

        approved = app.test_client()
        allowed = approved.post('/api/auth/login', json={
            'username': 'deputy', 'password': 'deputy-pass-1', 'access_code': code})
        assert allowed.status_code == 200, allowed.get_json()
        assert allowed.get_json()['success'] is True
        with approved.session_transaction() as session:
            assert session['access_approved'] is True
            assert session['owner_epoch'] == owner.epoch()

        # A used code cannot be replayed.
        replay = app.test_client().post('/api/auth/login', json={
            'username': 'deputy', 'password': 'deputy-pass-1', 'access_code': code})
        assert replay.status_code == 403
    finally:
        db_pool.execute_dml("DELETE FROM app_user WHERE user_id = %s", (user_id,))


def test_administrator_login_is_closed_when_no_master_key_exists(app):
    import bcrypt
    digest = bcrypt.hashpw(b'deputy-pass-1', bcrypt.gensalt()).decode()
    db_pool.execute_dml(
        "INSERT INTO app_user (username, password_hash, role) VALUES (%s, %s, 'admin')",
        ('deputy', digest))
    user_id = db_pool.execute_query("SELECT user_id FROM app_user WHERE username = 'deputy'", fetch='val')
    try:
        blocked = app.test_client().post('/api/auth/login', json={
            'username': 'deputy', 'password': 'deputy-pass-1'})
        assert blocked.status_code == 403
        assert blocked.get_json()['code'] == 'owner_blocked'
    finally:
        db_pool.execute_dml("DELETE FROM app_user WHERE user_id = %s", (user_id,))


def test_students_and_faculty_never_need_a_code(app):
    """The gate applies to administrators only."""
    import bcrypt
    owner.set_master_key(MASTER)
    digest = bcrypt.hashpw(b'gate-check-pass', bcrypt.gensalt()).decode()
    student_id = db_pool.execute_query(
        "SELECT student_id FROM student WHERE status = 'Active' LIMIT 1", fetch='val')
    faculty_id = db_pool.execute_query(
        "SELECT faculty_id FROM faculty WHERE status = 'Active' LIMIT 1", fetch='val')
    db_pool.execute_dml(
        "INSERT INTO app_user (username, password_hash, role, student_id) VALUES (%s, %s, 'student', %s)",
        ('gate-student', digest, student_id))
    db_pool.execute_dml(
        "INSERT INTO app_user (username, password_hash, role, faculty_id) VALUES (%s, %s, 'faculty', %s)",
        ('gate-faculty', digest, faculty_id))
    try:
        student = app.test_client().post('/api/auth/login', json={
            'username': 'gate-student', 'password': 'gate-check-pass'})
        assert student.status_code == 200, student.get_json()
        faculty = app.test_client().post('/api/auth/login', json={
            'username': 'gate-faculty', 'password': 'gate-check-pass'})
        assert faculty.status_code == 200, faculty.get_json()
    finally:
        db_pool.execute_dml("DELETE FROM app_user WHERE username IN ('gate-student', 'gate-faculty')")


# ---------------------------------------------------------------------------
# lockdown
# ---------------------------------------------------------------------------
def test_lockdown_signs_out_every_other_administrator(app):
    owner.set_master_key(MASTER)
    before = owner.epoch()

    other = second_admin_client(app, 'deputy')
    assert other.get('/dashboard').status_code == 200

    mine = client_for(app, 'admin', access_approved=True)
    assert mine.get('/admin-access').status_code == 200

    locked = mine.post('/admin-access/lockdown', data={'master_key': MASTER})
    assert locked.status_code == 302

    # The owner keeps working...
    assert mine.get('/dashboard').status_code == 200
    assert mine.get('/admin-access').status_code == 200
    # ...everybody else is out, on their very next request.
    thrown_out = other.get('/dashboard')
    assert thrown_out.status_code == 302
    assert '/login' in thrown_out.headers['Location']
    assert other.get('/raw-data').status_code == 302
    assert owner.epoch() == before + 1


def test_lockdown_needs_the_master_key(app):
    owner.set_master_key(MASTER)
    before = owner.epoch()
    mine = client_for(app, 'admin', access_approved=True)
    response = mine.post('/admin-access/lockdown', data={'master_key': 'not-the-key'})
    assert response.status_code == 302
    assert owner.epoch() == before
    assert mine.get('/dashboard').status_code == 200


def test_administrator_without_approval_is_logged_out_on_the_next_request(app):
    owner.set_master_key(MASTER)
    unapproved = second_admin_client(app, 'deputy')
    with unapproved.session_transaction() as session:
        session['access_approved'] = False
    response = unapproved.get('/dashboard')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']


def test_api_requests_get_a_json_refusal(app):
    owner.set_master_key(MASTER)
    stale = second_admin_client(app, 'deputy')
    owner.lockdown('admin')
    response = stale.post('/api/students', json={'first_name': 'X'})
    assert response.status_code == 401
    body = response.get_json()
    assert body['code'] == 'owner_signed_out'


# ---------------------------------------------------------------------------
# the owner page
# ---------------------------------------------------------------------------
def test_only_the_owner_can_open_the_page(app):
    owner.set_master_key(MASTER)
    assert second_admin_client(app, 'deputy').get('/admin-access').status_code == 403
    assert client_for(app, 'faculty', 'faculty', faculty_id=1).get('/admin-access').status_code == 403
    assert client_for(app, 'student', 'student', student_id=1).get('/admin-access').status_code == 403
    assert app.test_client().get('/admin-access').status_code == 302


def test_page_shows_key_state_and_requests(app):
    mine = client_for(app, 'admin', access_approved=True)
    empty = mine.get('/admin-access')
    assert empty.status_code == 200
    assert b'Create master key' in empty.data

    owner.set_master_key(MASTER)
    owner.request_access('deputy', user_id=99)
    page = mine.get('/admin-access')
    assert page.status_code == 200
    assert b'Sign out everyone else' in page.data
    assert b'deputy' in page.data
    assert b'Issue one-time code' in page.data
    assert MASTER.encode() not in page.data
    assert b'$2b$' not in page.data


def test_owner_issues_a_code_through_the_page(app):
    owner.set_master_key(MASTER)
    request_id = owner.request_access('deputy', user_id=99)
    mine = client_for(app, 'admin', access_approved=True)
    response = mine.post('/admin-access/issue', data={'master_key': MASTER, 'request_id': request_id})
    assert response.status_code == 302
    shown = mine.get('/admin-access')
    assert b'Access code for' in shown.data
    assert b'deputy' in shown.data

    wrong = mine.post('/admin-access/issue', data={'master_key': 'nope', 'request_id': request_id})
    assert wrong.status_code == 302


def test_owner_can_create_and_rotate_the_master_key_through_the_page(app):
    mine = client_for(app, 'admin', access_approved=True)
    created = mine.post('/admin-access/master-key', data={'new_key': 'first-master-key'})
    assert created.status_code == 302
    assert owner.verify_master_key('first-master-key')

    # Rotation requires the current key.
    refused = mine.post('/admin-access/master-key', data={'master_key': 'wrong', 'new_key': 'second-master-key'})
    assert refused.status_code == 302
    assert owner.verify_master_key('first-master-key')

    rotated = mine.post('/admin-access/master-key', data={'master_key': 'first-master-key',
                                                          'new_key': 'second-master-key'})
    assert rotated.status_code == 302
    assert owner.verify_master_key('second-master-key')
    assert not owner.verify_master_key('first-master-key')


def test_navigation_link_is_only_for_the_owner(app):
    owner.set_master_key(MASTER)
    assert b'/admin-access' in client_for(app, 'admin', access_approved=True).get('/dashboard').data
    assert b'/admin-access' not in second_admin_client(app, 'deputy').get('/dashboard').data
    assert b'/admin-access' not in client_for(app, 'faculty', 'faculty', faculty_id=1).get('/dashboard').data
