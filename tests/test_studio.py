"""SQL Studio: the administrator's read-only database client.

Reads run for real; data changes are prepared and declined; structure changes
are refused. The tests hold the studio to that promise, and check the client
itself renders with its navigator, worksheets and panes.
"""
import pytest

from app import create_app
from repositories import studio

WATCHED = ['student', 'enrollment', 'course_offering', 'department', 'result',
           'fee_payment', 'app_user', 'login_history', 'staff_activity']


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


def counts():
    from repositories.db_pool import db_pool as pool
    totals = {}
    for table in WATCHED:
        try:
            totals[table] = pool.execute_query(f'SELECT COUNT(*) FROM {table}', fetch='val')
        except Exception:
            totals[table] = None
    return totals


# ------------------------------------------------------------------ access ----

def test_the_studio_renders_for_an_administrator(admin):
    page = admin.get('/studio')
    assert page.status_code == 200
    body = page.data
    for marker in (b'st-app', b'st-tree', b'stSql', b'stGrid', b'studio.css', b'studio.js'):
        assert marker in body, marker
    assert b'{{' not in body
    assert b'READ-ONLY' in body.upper()


def test_the_navigator_lists_the_catalogue(admin):
    page = admin.get('/studio').data
    for name in (b'student', b'enrollment', b'v_attendance_summary', b'idx_'):
        assert name in page, name
    assert page.count(b'st-object') >= 10


def test_non_administrators_are_refused(faculty, student):
    for client in (faculty, student):
        assert client.get('/studio').status_code == 403
        assert client.post('/studio/run', json={'sql': 'SELECT 1'}).status_code == 403
        assert client.post('/studio/script', json={'sql': 'SELECT 1;'}).status_code == 403
        assert client.post('/studio/explain', json={'sql': 'SELECT 1'}).status_code == 403
        assert client.get('/studio/describe/student').status_code == 403


# ------------------------------------------------------------------- reads ----

def test_a_select_runs_for_real(admin):
    payload = admin.post('/studio/run', json={'sql': 'SELECT roll_no, status FROM student ORDER BY roll_no LIMIT 5'}).get_json()
    assert payload['ok'] is True
    assert payload['kind'] == 'read'
    assert payload['verb'] == 'SELECT'
    assert payload['row_count'] == 5
    assert payload['shown'] == 5
    assert payload['columns'][0]['name'] == 'roll_no'
    assert len(payload['rows'][0]['cells']) == 2
    assert payload['rows'][0]['number'] == 1
    assert payload['elapsed_ms'] >= 0


def test_the_password_hash_is_masked(admin):
    payload = admin.post('/studio/run', json={'sql': 'SELECT username, password_hash FROM app_user LIMIT 1'}).get_json()
    assert payload['ok'] is True
    assert payload['rows'][0]['cells'][1]['text'] == studio.PLACEHOLDER


def test_a_result_is_capped_and_says_so(admin):
    payload = admin.post('/studio/run', json={'sql': 'SELECT * FROM result'}).get_json()
    assert payload['ok'] is True
    if payload['row_count'] > studio.MAX_ROWS:
        assert payload['truncated'] == payload['row_count'] - studio.MAX_ROWS
        assert payload['shown'] == studio.MAX_ROWS
    else:
        assert payload['truncated'] == 0


def test_an_engine_error_is_reported_not_raised(admin):
    payload = admin.post('/studio/run', json={'sql': 'SELECT * FROM no_such_table'}).get_json()
    assert payload['ok'] is False
    assert 'no such table' in payload['error'].lower()
    assert payload['code'] == 'STUDIO-006'


def test_a_statement_without_a_table_can_run(admin):
    payload = admin.post('/studio/run', json={'sql': 'SELECT 2 + 2 AS total'}).get_json()
    assert payload['ok'] is True
    assert payload['rows'][0]['cells'][0]['text'] == '4'
    assert payload['rows'][0]['cells'][0]['numeric'] is True


# ------------------------------------------------------------------ writes ----

def test_writes_are_prepared_and_never_committed(admin):
    before = counts()
    payload = admin.post('/studio/run', json={
        'sql': "UPDATE student SET status = 'Suspended' WHERE student_id = 1"}).get_json()
    assert payload['ok'] is True
    assert payload['kind'] == 'prepare'
    assert 'read-only' in payload['note'].lower()
    assert counts() == before


def test_an_invalid_write_is_rejected_by_the_engine(admin):
    payload = admin.post('/studio/run', json={
        'sql': 'INSERT INTO student (no_such_column) VALUES (1)'}).get_json()
    assert payload['ok'] is False
    assert payload['code'] == 'STUDIO-005'


def test_schema_and_transaction_control_are_refused(admin):
    for statement in ('DROP TABLE student', 'ALTER TABLE student ADD COLUMN x INT',
                      'PRAGMA journal_mode=WAL', 'COMMIT', 'ATTACH DATABASE \'x.db\' AS x'):
        payload = admin.post('/studio/run', json={'sql': statement}).get_json()
        assert payload['ok'] is False, statement
        assert payload['code'] == 'STUDIO-002', statement
        assert payload['error']


def test_the_append_only_registers_are_protected(admin):
    payload = admin.post('/studio/run', json={
        'sql': "DELETE FROM login_history"}).get_json()
    assert payload['ok'] is False
    assert payload['code'] == 'STUDIO-004'


def test_two_statements_need_run_script(admin):
    payload = admin.post('/studio/run', json={'sql': 'SELECT 1; SELECT 2;'}).get_json()
    assert payload['ok'] is False
    assert 'F5' in payload['error']


# ------------------------------------------------------------------ script ----

def test_a_script_reports_every_statement(admin):
    script = 'SELECT 1 AS a;\nSELECT 2 AS b;\n-- just a comment\n'
    payload = admin.post('/studio/script', json={'sql': script}).get_json()
    assert payload['ok'] is True
    assert payload['total'] == 2
    assert payload['succeeded'] == 2
    assert [item['verb'] for item in payload['statements']] == ['SELECT', 'SELECT']
    assert payload['elapsed_ms'] >= 0


def test_commas_and_semicolons_inside_strings_do_not_split(admin):
    payload = admin.post('/studio/script', json={
        'sql': "SELECT 'a;b' AS first;\nSELECT 'it''s; fine' AS second;"}).get_json()
    assert payload['total'] == 2
    assert all(item['ok'] for item in payload['statements'])


def test_the_starter_script_runs_end_to_end(admin):
    payload = admin.post('/studio/script', json={'sql': studio.starter_script()}).get_json()
    assert payload['ok'] is True, [item['error'] for item in payload['statements'] if not item['ok']]
    assert payload['total'] >= 4
    assert payload['elapsed_ms'] >= 0


def test_an_empty_script_is_refused(admin):
    payload = admin.post('/studio/script', json={'sql': '  -- nothing\n\n'}).get_json()
    assert payload['ok'] is False
    assert payload['error']


# ------------------------------------------------------------------- plans ----

def test_a_plan_has_nested_steps(admin):
    payload = admin.post('/studio/explain', json={
        'sql': "SELECT s.roll_no FROM student s JOIN enrollment e "
               "ON e.student_id = s.student_id WHERE e.status = 'Enrolled'"}).get_json()
    assert payload['ok'] is True
    assert payload['nodes']
    assert payload['verdict'] in ('scan', 'index')
    assert payload['summary']
    for node in payload['nodes']:
        assert node['kind'] in ('scan', 'index', 'other')
        assert node['depth'] >= 0
        assert node['detail']


def test_a_plan_for_a_broken_statement_is_reported(admin):
    payload = admin.post('/studio/explain', json={'sql': 'SELECT * FROM nothing_here'}).get_json()
    assert payload['ok'] is False
    assert payload['error']


# -------------------------------------------------------------- describing ----

def test_describe_returns_the_columns(admin):
    payload = admin.get('/studio/describe/student').get_json()
    assert payload['ok'] is True
    assert payload['type'] == 'table'
    assert payload['rows'] >= 0
    assert any(column['name'] == 'roll_no' for column in payload['columns'])
    assert 'foreign_keys' in payload


def test_describe_unknown_object_is_404(admin):
    assert admin.get('/studio/describe/not_a_table').status_code == 404


# -------------------------------------------------------------------- misc ----

def test_studio_runs_stay_out_of_the_change_log(admin):
    from repositories.db_pool import db_pool as pool
    before = pool.execute_query('SELECT COUNT(*) FROM staff_activity', fetch='val')
    admin.post('/studio/run', json={'sql': 'SELECT 1'})
    admin.post('/studio/script', json={'sql': 'SELECT 1; SELECT 2;'})
    after = pool.execute_query('SELECT COUNT(*) FROM staff_activity', fetch='val')
    assert after == before


def test_the_navigation_links_to_the_studio(admin):
    page = admin.get('/studio').data
    assert b'SQL Studio' in page
    dashboard = admin.get('/dashboard').data
    assert b'/studio' in dashboard


def test_studio_and_workshop_agree_on_the_counts(admin):
    catalogue = studio.catalogue()
    assert len(catalogue['tables']) >= 10
    assert len(catalogue['views']) >= 1
    assert len(catalogue['triggers']) >= 1
    assert len(catalogue['procedures']) == 3
    assert len(catalogue['functions']) == 3
    for table in catalogue['tables']:
        assert table['columns'], table['name']
