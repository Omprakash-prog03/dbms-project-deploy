"""The rotating six-digit code: one number for everyone, changed every ten minutes."""
import hmac
from datetime import datetime, timedelta

import bcrypt
import pytest

from app import create_app
from config import Config
from repositories import admin_sessions, login_history, owner, staff_activity
from repositories.db_pool import db_pool

PASSWORD = 'deputy-pass-1'


@pytest.fixture(autouse=True)
def fresh_guard(monkeypatch):
    from repositories.owner import GUARD_TABLE, REQUEST_TABLE
    owner.ensure_schema()
    admin_sessions.ensure_schema()
    db_pool.execute_dml(f'DELETE FROM {REQUEST_TABLE}')
    db_pool.execute_dml(f'DELETE FROM {GUARD_TABLE}')
    db_pool.execute_dml(f'DELETE FROM {admin_sessions.TABLE}')
    db_pool.execute_dml("DELETE FROM app_user WHERE username IN ('om-2026', 'deputy')")
    monkeypatch.setattr(owner, '_ready', False)
    yield
    for account in ('om-2026', 'deputy'):
        db_pool.execute_dml('DELETE FROM app_user WHERE username = %s', (account,))
        db_pool.execute_dml('DELETE FROM admin_session WHERE username = %s', (account,))
    db_pool.execute_dml(f'DELETE FROM {admin_sessions.TABLE}')
    db_pool.execute_dml(f'DELETE FROM {GUARD_TABLE}')
    db_pool.execute_dml(f'DELETE FROM {REQUEST_TABLE}')
    owner._ready = False
    staff_activity._ready = False
    login_history._ready = False


@pytest.fixture
def app():
    return create_app({'TESTING': True, 'CSRF_ENABLED': False, 'RATELIMIT_ENABLED': False})


def add_admin(username, password=PASSWORD):
    digest = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    db_pool.execute_dml("DELETE FROM app_user WHERE username = %s", (username,))
    db_pool.execute_dml(
        "INSERT INTO app_user (username, password_hash, role) VALUES (%s, %s, 'admin')",
        (username, digest))


def supreme_client(app):
    add_admin('om-2026', 'Superadmin123')
    client = app.test_client()
    with client.session_transaction() as session:
        session.update(user_id=99, username='om-2026', role='admin', access_approved=True,
                       supreme=True, owner_epoch=owner.epoch(),
                       admin_token_version=admin_sessions.version('om-2026'))
    return client


def sign_in(app, username='deputy', code=''):
    return app.test_client().post('/api/auth/login', json={
        'username': username, 'password': PASSWORD, 'access_code': code})


# ---------------------------------------------------------------------------
# the number itself
# ---------------------------------------------------------------------------
def test_the_code_is_six_digits_and_stays_put_for_ten_minutes(monkeypatch):
    base = datetime(2026, 5, 4, 9, 0, 0)
    monkeypatch.setattr(owner, '_now', lambda: base)
    first = owner.rotating_code()
    assert len(first) == 6 and first.isdigit()

    monkeypatch.setattr(owner, '_now', lambda: base + timedelta(minutes=9, seconds=59))
    assert owner.rotating_code() == first, 'the number must not change mid-window'

    monkeypatch.setattr(owner, '_now', lambda: base + timedelta(minutes=10))
    assert owner.rotating_code() != first, 'a new number every ten minutes'


def test_the_countdown_reports_the_rest_of_the_window(monkeypatch):
    monkeypatch.setattr(owner, '_now', lambda: datetime(2026, 5, 4, 9, 0, 30))
    left = owner.rotating_seconds_left()
    assert 0 < left <= 600
    snapshot = owner.rotating_snapshot()
    assert snapshot['minutes'] == 10
    assert snapshot['seconds_left'] == left
    assert snapshot['enabled'] is True
    assert snapshot['code'] == owner.rotating_code()


def test_each_installation_gets_its_own_number():
    first = owner.rotating_code()
    db_pool.execute_dml(f"DELETE FROM {owner.GUARD_TABLE} WHERE guard_key = 'rotating_secret'")
    owner._ready = False
    assert owner.rotating_code() != first


def test_the_previous_window_is_still_accepted(monkeypatch):
    moment = datetime(2026, 5, 4, 9, 10, 2)
    monkeypatch.setattr(owner, '_now', lambda: moment)
    previous = owner.rotating_code(owner.rotating_window(moment - timedelta(minutes=10)))
    assert owner.verify_rotating_code(previous) is True
    assert owner.verify_rotating_code('000000' if previous != '000000' else '111111') is False
    assert owner.verify_rotating_code('12345') is False
    assert owner.verify_rotating_code('abcdef') is False


# ---------------------------------------------------------------------------
# signing in with it
# ---------------------------------------------------------------------------
def test_an_administrator_signs_in_with_username_password_and_the_number(app):
    owner.set_code_required(True)
    add_admin('deputy')
    response = sign_in(app, code=owner.rotating_code())
    assert response.status_code == 200, response.get_json()
    assert response.get_json()['success'] is True

    event = login_history.recent(limit=20)[0]
    assert event['username'] == 'deputy'
    assert event['event'] == login_history.SIGNED_IN
    assert 'rotating supreme code' in event['detail']


def test_a_wrong_number_is_refused(app):
    owner.set_code_required(True)
    add_admin('deputy')
    wrong = '000000' if owner.rotating_code() != '000000' else '111111'
    response = sign_in(app, code=wrong)
    assert response.status_code == 403
    assert 'rotating' in response.get_json()['message']


def test_the_rotating_sign_in_leaves_no_waiting_request(app):
    owner.set_code_required(True)
    add_admin('deputy')
    sign_in(app, code=owner.rotating_code())
    assert owner.pending_requests() == []


def test_the_switch_turns_it_off_and_personal_codes_still_work(app):
    owner.set_code_required(True)
    add_admin('deputy')
    owner.set_rotating_enabled(False)
    refused = sign_in(app, code=owner.rotating_code())
    assert refused.status_code == 403

    request_id = owner.request_access('deputy')
    code = owner.issue_code(request_id)['code']
    assert sign_in(app, code=code).status_code == 200


# ---------------------------------------------------------------------------
# the supreme page
# ---------------------------------------------------------------------------
def test_the_supreme_page_shows_the_number_and_the_countdown(app):
    client = supreme_client(app)
    body = client.get('/owner').get_data(as_text=True)
    assert 'Administrator sign-in code' in body
    assert owner.rotating_code() in body
    assert 'changes in' in body
    section = body[body.index('id="rotating-code"'):body.index('Access codes')]
    assert 'username and password' in section
    assert 'Require a code at sign-in' in section


def test_the_page_offers_the_switch_once_codes_are_on(app):
    client = supreme_client(app)
    owner.set_code_required(True)
    section = client.get('/owner').get_data(as_text=True)
    section = section[section.index('id="rotating-code"'):section.index('Access codes')]
    assert 'Switch codes off (password only)' in section
    assert 'Stop accepting the rotating number' in section


def test_the_live_endpoint_answers_for_the_supreme_only(app):
    client = supreme_client(app)
    payload = client.get('/owner/rotating-code').get_json()
    assert payload['code'] == owner.rotating_code()
    assert payload['enabled'] is True
    assert 0 < payload['seconds_left'] <= 600

    add_admin('deputy')
    other = app.test_client()
    with other.session_transaction() as session:
        session.update(user_id=98, username='deputy', role='admin', access_approved=True,
                       owner_epoch=owner.epoch(),
                       admin_token_version=admin_sessions.version('deputy'))
    assert other.get('/owner/rotating-code').status_code == 403
    assert app.test_client().get('/owner/rotating-code').status_code in (302, 401)


def test_the_switch_is_recorded_and_blocks_the_number(app):
    client = supreme_client(app)
    written = client.post('/owner/rotating-code/switch', data={'enabled': '0'})
    assert written.status_code == 302
    assert owner.rotating_enabled() is False
    trail = ' '.join(item['action'] for item in owner.trail(limit=10))
    assert 'rotating code off' in trail

    assert client.get('/owner/rotating-code').get_json()['enabled'] is False

    owner.set_code_required(True)
    add_admin('deputy')
    assert sign_in(app, code=owner.rotating_code()).status_code == 403


def test_the_page_says_when_the_rotating_number_is_not_accepted(app):
    client = supreme_client(app)
    owner.set_code_required(True)
    owner.set_rotating_enabled(False)
    body = client.get('/owner').get_data(as_text=True)
    section = body[body.index('id="rotating-code"'):body.index('Access codes')]
    assert 'Accept the rotating number' in section
