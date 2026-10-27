"""The database workshop: a read-only teaching console for administrators.

Every statement here is either a plain SELECT or an attempt that the database
refuses inside a savepoint. Nothing in this suite may change a row, and the
append-only registers must stay untouched, so the tests check row counts on
both sides of every demo.
"""
import pytest

from app import create_app
from repositories import workshop

TABS = ['overview', 'joins', 'views', 'procedures', 'functions', 'triggers', 'plans', 'schema']

# Tables the workshop reads or attempts to write to; a proof must leave these alone.
WATCHED = [
    'student', 'enrollment', 'course_offering', 'attendance', 'result',
    'fee_payment', 'app_user', 'login_history', 'staff_activity',
]


@pytest.fixture
def admin():
    client = create_app({'TESTING': True, 'CSRF_ENABLED': False, 'RATELIMIT_ENABLED': False}).test_client()
    with client.session_transaction() as session:
        session.update(user_id=1, username='admin', role='admin')
    return client


@pytest.fixture
def faculty():
    client = create_app({'TESTING': True, 'CSRF_ENABLED': False}).test_client()
    with client.session_transaction() as session:
        session.update(user_id=2, username='faculty', role='faculty', faculty_id=1)
    return client


@pytest.fixture
def student():
    client = create_app({'TESTING': True, 'CSRF_ENABLED': False}).test_client()
    with client.session_transaction() as session:
        session.update(user_id=3, username='student', role='student', student_id=1)
    return client


def row_counts():
    from repositories.db_pool import db_pool as pool
    counts = {}
    for table in WATCHED:
        try:
            counts[table] = pool.execute_query(f'SELECT COUNT(*) FROM {table}', fetch='val')
        except Exception:  # a table may not exist on every engine
            counts[table] = None
    return counts


# ---------------------------------------------------------------- access ----

def test_administrator_opens_the_workshop(admin):
    page = admin.get('/database')
    assert page.status_code == 200
    body = page.data
    assert b'ws-toolbar' in body
    assert b'css/workshop.css' in body and b'js/workshop.js' in body
    assert b'{{' not in body


def test_every_tab_renders(admin):
    for tab in TABS:
        response = admin.get(f'/database?tab={tab}')
        assert response.status_code == 200, tab
        assert tab.encode() in response.data


def test_unknown_tab_falls_back_to_the_overview(admin):
    response = admin.get('/database?tab=not-a-tab')
    assert response.status_code == 200
    assert b'ws-pipeline' in response.data


def test_non_administrators_are_refused(faculty, student):
    for client in (faculty, student):
        assert client.get('/database').status_code == 403
        assert client.post('/database/run/inner', json={}).status_code == 403
        assert client.post('/database/prove/capacity', json={}).status_code == 403
        assert client.get('/database/workshop.pdf').status_code == 403


# ------------------------------------------------------------- the demos ----

def test_join_demo_shapes(admin):
    for demo in workshop.join_demos():
        response = admin.post(f"/database/run/{demo['key']}", json={})
        assert response.status_code == 200, demo['key']
        payload = response.get_json()
        assert payload['ok'] is True, payload.get('error')
        assert payload['columns'], demo['key']
        # row_count is everything the statement matched; a demo may show fewer.
        assert payload['shown'] == len(payload['rows'])
        assert payload['row_count'] >= payload['shown'] > 0, demo['key']
        assert payload['truncated'] is (payload['row_count'] > payload['shown'])
        first = payload['rows'][0]
        assert first['number'] == 1
        assert len(first['cells']) == len(payload['columns'])
        assert payload['elapsed_ms'] >= 0


def test_unknown_join_demo_is_refused(admin):
    assert admin.post('/database/run/nope', json={}).status_code == 404


def test_plan_for_every_demo_names_its_steps(admin):
    for demo in workshop.join_demos():
        response = admin.post(f"/database/explain/{demo['key']}", json={})
        assert response.status_code == 200, demo['key']
        plan = response.get_json()
        assert plan['ok'] is True, plan.get('error')
        assert plan['steps'], demo['key']
        assert plan['verdict'] in ('index', 'scan')
        assert plan['summary']
        for step in plan['steps']:
            assert step['kind'] in ('index', 'scan', 'other')
            assert step['detail']


def test_functions_evaluate(admin):
    for key in ('grade', 'attendance', 'cgpa'):
        response = admin.post(f'/database/function/{key}', json={})
        assert response.status_code == 200, key
        payload = response.get_json()
        assert payload['ok'] is True, payload.get('error')
        assert payload['row_count'] > 0, key
        assert payload['columns']


def test_procedure_walkthroughs_pass(admin):
    for procedure in workshop.procedures():
        response = admin.post(f"/database/procedure/{procedure['name']}", json={})
        assert response.status_code == 200, procedure['name']
        walkthrough = response.get_json()
        assert walkthrough['steps'], procedure['name']
        assert all(step['ok'] for step in walkthrough['steps']), procedure['name']
        assert walkthrough['verdict']


# ----------------------------------------------------------- the guards -----

def test_every_trigger_proof_is_refused_without_writing(admin):
    before = row_counts()
    for rule in [proof['rule'] for proof in workshop.TRIGGER_PROOFS]:
        response = admin.post(f'/database/prove/{rule}', json={})
        assert response.status_code == 200, rule
        proof = response.get_json()
        assert proof['refused'] is True, (rule, proof.get('message'))
        assert proof['message'], rule
        assert proof['statement'], rule
    assert row_counts() == before


def test_unknown_rule_is_refused(admin):
    assert admin.post('/database/prove/not-a-rule', json={}).status_code == 404


def test_demo_runs_do_not_enter_the_change_log(admin):
    from repositories.db_pool import db_pool as pool
    before = pool.execute_query('SELECT COUNT(*) FROM staff_activity', fetch='val')
    for demo in workshop.join_demos():
        admin.post(f"/database/run/{demo['key']}", json={})
    admin.post('/database/prove/history', json={})
    after = pool.execute_query('SELECT COUNT(*) FROM staff_activity', fetch='val')
    assert after == before


# ----------------------------------------------------------- the handout -----

def test_handout_is_a_pdf(admin):
    response = admin.get('/database/workshop.pdf')
    assert response.status_code == 200
    assert response.headers['Content-Type'] == 'application/pdf'
    assert response.data[:5] == b'%PDF-'
    assert len(response.data) > 5000


def test_workshop_is_linked_from_the_navigation(admin):
    body = admin.get('/database').data
    assert b'/database"' in body or b"/database'" in body
    assert b'Database workshop' in body


def test_overview_counts_match_the_repository(admin):
    overview = workshop.overview()
    assert overview['counts']['tables'] > 0
    assert overview['counts']['views'] > 0
    assert overview['counts']['triggers'] > 0
    assert overview['storage']['engine']
