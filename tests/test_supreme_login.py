"""The supreme sign-in page, the code rule, and removing an administrator."""
import bcrypt
import pytest

from app import create_app
from config import Config
from repositories import admin_sessions, owner
from repositories.db_pool import db_pool

SUPREME = ('om-2026', 'Superadmin123')
MASTER = 'supreme-master-key-9876'


@pytest.fixture(autouse=True)
def clean_state(monkeypatch):
    from repositories.owner import GUARD_TABLE, REQUEST_TABLE
    monkeypatch.setattr(Config, 'OWNER_USERNAME', 'om-2026')
    monkeypatch.setattr(Config, 'OTP_EXEMPT_ADMINS', 'omprakash')
    owner.ensure_schema()
    admin_sessions.ensure_schema()
    db_pool.execute_dml(f'DELETE FROM {REQUEST_TABLE}')
    db_pool.execute_dml(f'DELETE FROM {GUARD_TABLE}')
    db_pool.execute_dml(f'DELETE FROM {admin_sessions.TABLE}')
    db_pool.execute_dml(
        "DELETE FROM app_user WHERE username IN "
        "('om-2026', 'omprakash', 'swaruppradhan', 'avashbadatya', 'aryandash')")
    yield
    db_pool.execute_dml(f'DELETE FROM {REQUEST_TABLE}')
    db_pool.execute_dml(f'DELETE FROM {GUARD_TABLE}')
    db_pool.execute_dml(f'DELETE FROM {admin_sessions.TABLE}')
    db_pool.execute_dml(
        "DELETE FROM app_user WHERE username IN "
        "('om-2026', 'omprakash', 'swaruppradhan', 'avashbadatya', 'aryandash')")


@pytest.fixture
def app():
    return create_app({'TESTING': True, 'CSRF_ENABLED': False, 'RATELIMIT_ENABLED': False})


def make_admin(username, password):
    digest = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    db_pool.execute_dml(
        "INSERT INTO app_user (username, password_hash, role) VALUES (%s, %s, 'admin')",
        (username, digest))
    return db_pool.execute_query('SELECT user_id FROM app_user WHERE username = %s',
                                 (username,), fetch='val')


def supreme_account():
    return make_admin(*SUPREME)


def sign_in_supreme(app, password=SUPREME[1], client=None):
    client = client or app.test_client()
    return client.post('/supreme/login', data={'username': SUPREME[0], 'password': password})


def owner_client(app):
    client = app.test_client()
    with client.session_transaction() as session:
        session.update(user_id=99, username='om-2026', role='admin', access_approved=True,
                       supreme=True, owner_epoch=owner.epoch(),
                       admin_token_version=admin_sessions.version('om-2026'))
    return client


# ---------------------------------------------------------------------------
# the page itself
# ---------------------------------------------------------------------------
def test_supreme_page_is_its_own_door(app):
    page = app.test_client().get('/supreme')
    assert page.status_code == 200
    body = page.get_data(as_text=True)
    assert 'Supreme access' in body
    assert 'id="supremeUsername"' in body
    assert 'id="supremePassword"' in body
    assert 'noindex' in body
    # It points everyone else back at the campus sign-in.
    assert '/login' in body


def test_supreme_page_sends_a_signed_in_supreme_straight_to_the_dashboard(app):
    supreme_account()
    client = app.test_client()
    signed_in = sign_in_supreme(app, client=client)
    assert signed_in.location.endswith('/owner')
    page = client.get('/supreme')
    assert page.status_code == 302
    assert page.headers['Location'].endswith('/owner')


def test_supreme_sign_in_accepts_only_the_supreme_account(app):
    supreme_account()
    make_admin('swaruppradhan', 'Adminpradhan123')

    wrong_password = sign_in_supreme(app, password='not-the-password')
    assert wrong_password.status_code == 302
    assert wrong_password.headers['Location'].endswith('/supreme')

    ordinary_admin = app.test_client().post('/supreme/login', data={
        'username': 'swaruppradhan', 'password': 'Adminpradhan123'})
    assert ordinary_admin.headers['Location'].endswith('/supreme')

    unknown = app.test_client().post('/supreme/login', data={
        'username': 'nobody', 'password': 'whatever-123'})
    assert unknown.headers['Location'].endswith('/supreme')

    # Nobody was signed in by the failed attempts.
    assert app.test_client().get('/owner').status_code == 302


def test_supreme_sign_in_opens_the_dashboard(app):
    supreme_account()
    client = app.test_client()
    sign_in_supreme(app, client=client)
    dashboard = client.get('/owner')
    assert dashboard.status_code == 200
    assert b'You are the supreme administrator' in dashboard.data
    assert b'om-2026' in dashboard.data


def test_the_supreme_account_is_refused_on_the_campus_sign_in(app):
    supreme_account()
    refused = app.test_client().post('/api/auth/login', json={
        'username': 'om-2026', 'password': 'Superadmin123'})
    assert refused.status_code == 403
    payload = refused.get_json()
    assert payload['code'] == 'use_supreme_page'
    assert payload['redirect'].endswith('/supreme')


def test_admin_access_address_redirects_a_guest_to_the_supreme_page(app):
    guest = app.test_client().get('/owner')
    assert guest.status_code == 302
    assert guest.headers['Location'].endswith('/supreme')


# ---------------------------------------------------------------------------
# who needs a code
# ---------------------------------------------------------------------------
def test_every_administrator_but_the_exempt_ones_needs_a_code(app):
    supreme_account()
    make_admin('omprakash', 'Adminom123')
    make_admin('swaruppradhan', 'Adminpradhan123')

    exempt = app.test_client().post('/api/auth/login', json={
        'username': 'omprakash', 'password': 'Adminom123'})
    assert exempt.status_code == 200, exempt.get_data(as_text=True)
    assert exempt.get_json()['redirect'].endswith('/dashboard')

    needs_code = app.test_client().post('/api/auth/login', json={
        'username': 'swaruppradhan', 'password': 'Adminpradhan123'})
    assert needs_code.status_code == 403
    assert needs_code.get_json()['code'] == 'approval_required'

    pending = owner.pending_requests()
    assert [item['username'] for item in pending] == ['swaruppradhan']
    code = owner.issue_code(pending[0]['request_id'])['code']
    signed_in = app.test_client().post('/api/auth/login', json={
        'username': 'swaruppradhan', 'password': 'Adminpradhan123', 'access_code': code})
    assert signed_in.status_code == 200


def test_a_used_code_does_not_work_twice(app):
    supreme_account()
    make_admin('avashbadatya', 'Adminavash123')
    request_id = owner.request_access('avashbadatya', user_id=99)
    code = owner.issue_code(request_id)['code']
    first = app.test_client().post('/api/auth/login', json={
        'username': 'avashbadatya', 'password': 'Adminavash123', 'access_code': code})
    assert first.status_code == 200
    again = app.test_client().post('/api/auth/login', json={
        'username': 'avashbadatya', 'password': 'Adminavash123', 'access_code': code})
    assert again.status_code == 403
    assert again.get_json()['code'] == 'approval_required'


def test_status_endpoint_knows_the_exempt_and_supreme_accounts(app):
    supreme_account()
    make_admin('omprakash', 'Adminom123')
    make_admin('aryandash', 'Adminaryan123')
    client = app.test_client()
    assert client.post('/api/auth/access-status', json={'username': 'om-2026'}).get_json()['state'] == 'owner'
    assert client.post('/api/auth/access-status', json={'username': 'omprakash'}).get_json()['state'] == 'not-required'
    assert client.post('/api/auth/access-status', json={'username': 'aryandash'}).get_json()['state'] == 'none'


def test_dashboard_names_the_exempt_administrators(app):
    supreme_account()
    make_admin('omprakash', 'Adminom123')
    page = owner_client(app).get('/owner')
    body = page.get_data(as_text=True)
    assert 'omprakash' in body
    assert 'no code needed' in body
    assert 'is exempt' in body


# ---------------------------------------------------------------------------
# the supreme power: end a session, remove an account
# ---------------------------------------------------------------------------
def test_removing_an_administrator_who_is_signed_in(app):
    supreme_account()
    admin_id = make_admin('aryandash', 'Adminaryan123')
    owner.set_master_key(MASTER)

    # They sign in (with a code), so they are live on the site.
    request_id = owner.request_access('aryandash', user_id=admin_id)
    code = owner.issue_code(request_id)['code']
    their_client = app.test_client()
    assert their_client.post('/api/auth/login', json={
        'username': 'aryandash', 'password': 'Adminaryan123', 'access_code': code}).status_code == 200
    assert their_client.get('/dashboard').status_code == 200
    signed_in = [a['username'] for a in admin_sessions.overview('om-2026') if a['signed_in']]
    assert 'aryandash' in signed_in

    # The supreme administrator removes the account entirely.
    mine = owner_client(app)
    mine.post('/owner/remove/aryandash', data={'master_key': MASTER})

    assert db_pool.execute_query(
        "SELECT user_id FROM app_user WHERE username = 'aryandash'", fetch='one') is None
    assert their_client.get('/dashboard').status_code == 302
    assert 'aryandash' not in [a['username'] for a in admin_sessions.overview('om-2026')]
    assert b'aryandash is no longer an administrator' in mine.get('/owner').data
    # The record of it survives.
    assert any('removed' in entry['action'] for entry in owner.trail(limit=20))


def test_signing_one_administrator_out_leaves_the_others_alone(app):
    supreme_account()
    make_admin('swaruppradhan', 'Adminpradhan123')
    make_admin('avashbadatya', 'Adminavash123')
    owner.set_master_key(MASTER)

    clients = {}
    for name, password in (('swaruppradhan', 'Adminpradhan123'), ('avashbadatya', 'Adminavash123')):
        request_id = owner.request_access(name, user_id=99)
        code = owner.issue_code(request_id)['code']
        clients[name] = app.test_client()
        assert clients[name].post('/api/auth/login', json={
            'username': name, 'password': password, 'access_code': code}).status_code == 200

    owner_client(app).post('/owner/sign-out/swaruppradhan')
    assert clients['swaruppradhan'].get('/dashboard').status_code == 302
    assert clients['avashbadatya'].get('/dashboard').status_code == 200


def test_master_key_is_optional_for_issuing_codes(app):
    supreme_account()
    make_admin('swaruppradhan', 'Adminpradhan123')
    assert not owner.master_key_set()
    mine = owner_client(app)

    request_id = owner.request_access('swaruppradhan', user_id=99)
    response = mine.post('/owner/issue', data={'request_id': request_id})
    assert response.status_code == 302
    with mine.session_transaction() as session:
        issued = session.get('issued_code')
    assert issued and len(issued['code']) == 6
