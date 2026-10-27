"""Oracle SQL everywhere, and the change journal that makes a real edit reversible.

Two promises are checked here:

* the portal accepts Oracle syntax on every screen — `ROWNUM`, `DUAL`, `NVL`,
  `DECODE`, `TO_CHAR`, `SYSDATE`, `FETCH FIRST`, `MINUS`, `LISTAGG` — while an
  ordinary statement passes through byte for byte;
* every writable statement in the practice schema can be taken back, and then
  replayed.
"""
import pytest

from app import create_app
from repositories import dialect, oracle
from repositories.db_pool import db_pool


@pytest.fixture(autouse=True)
def practice(tmp_path, monkeypatch):
    monkeypatch.setenv('STUDIO_ORACLE_PATH', str(tmp_path / 'practice.db'))
    oracle.reset()
    yield


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


# ---------------------------------------------------------- dialect: portal ----

def test_rownum_limits_a_portal_query():
    rows = db_pool.execute_query('SELECT roll_no FROM student WHERE ROWNUM <= 3', fetch='all')
    assert len(rows) == 3


def test_dual_and_nvl_run_against_the_portal():
    row = db_pool.execute_query("SELECT NVL(NULL, 'fallback') AS value FROM dual", fetch='one')
    assert row['value'] == 'fallback'


def test_fetch_first_and_offset_are_understood():
    first = db_pool.execute_query('SELECT dept_code FROM department ORDER BY dept_code FETCH FIRST 2 ROWS ONLY', fetch='all')
    assert len(first) == 2
    later = db_pool.execute_query(
        'SELECT dept_code FROM department ORDER BY dept_code OFFSET 2 ROWS FETCH NEXT 2 ROWS ONLY', fetch='all')
    assert len(later) == 2 and later[0] != first[0]


def test_decode_and_to_char_are_understood():
    rows = db_pool.execute_query(
        "SELECT DECODE(status, 'Active', 'A', 'B') AS band, COUNT(*) AS total "
        'FROM student GROUP BY status FETCH FIRST 2 ROWS ONLY', fetch='all')
    assert rows and all(row['band'] in ('A', 'B') for row in rows)
    months = db_pool.execute_query(
        "SELECT TO_CHAR(admission_date, 'YYYY-MM') AS month FROM student "
        'WHERE admission_date IS NOT NULL FETCH FIRST 2 ROWS ONLY', fetch='all')
    assert all('-' in row['month'] for row in months)


def test_minus_and_listagg_are_understood():
    remaining = db_pool.execute_query(
        "SELECT dept_code FROM department MINUS SELECT dept_code FROM department WHERE dept_code = 'CSE'",
        fetch='all')
    assert 'CSE' not in {row['dept_code'] for row in remaining}

    grouped = db_pool.execute_query(
        "SELECT dept_code, LISTAGG(dept_name, ', ') WITHIN GROUP (ORDER BY dept_name) AS names "
        'FROM department GROUP BY dept_code FETCH FIRST 2 ROWS ONLY', fetch='all')
    assert grouped and ',' not in grouped[0]['dept_code']


def test_plain_sql_is_passed_through_untouched():
    sql = 'SELECT roll_no FROM student ORDER BY roll_no LIMIT 2'
    assert dialect.to_engine(sql) == (sql, [])
    assert dialect.looks_oracle(sql) is False


def test_a_string_that_mentions_an_oracle_word_is_not_translated():
    sql = "SELECT 'NVL and DUAL are words' AS note FROM dual"
    engine_sql, _notes = dialect.to_engine(sql)
    assert 'the engine' not in engine_sql
    assert "SELECT 'NVL and DUAL are words' AS note FROM (SELECT 1 AS DUMMY)" == engine_sql


def test_the_layer_can_be_switched_off(monkeypatch):
    monkeypatch.setattr('config.Config.DB_DIALECT', 'native')
    sql = 'SELECT 1 FROM dual'
    assert dialect.to_engine(sql) == (sql, [])


def test_the_practice_connection_uses_the_same_translator_with_its_own_rules():
    payload = oracle.run('SELECT USER, SYSDATE FROM dual')
    assert payload['rows'][0]['cells'][0]['text'] == 'STUDIO'
    # sequences stay a practice-schema idea: the portal translator never advances one
    _, notes = dialect.to_engine('SELECT emp_seq.NEXTVAL FROM dual')
    assert notes == []


def test_a_pseudocolumn_is_named_the_oracle_way():
    assert oracle.pseudocolumn_label("datetime('now')") == 'SYSDATE'
    assert oracle.pseudocolumn_label("'PORTAL'") == 'USER'
    assert oracle.pseudocolumn_label('roll_no') == 'roll_no'


def test_the_studio_portal_connection_accepts_oracle_sql(admin):
    payload = admin.post('/studio/run', json={'sql': 'SELECT roll_no FROM student WHERE ROWNUM <= 2'}).get_json()
    assert payload['ok'] and payload['row_count'] == 2
    assert payload['translated'] and 'LIMIT 2' in payload['translated']
    assert payload['notes']


def test_the_portal_stays_read_only_under_oracle_syntax(admin):
    payload = admin.post('/studio/run', json={
        'sql': "INSERT INTO department (dept_code, dept_name) VALUES ('ZZZ', 'Nope')"}).get_json()
    assert payload['ok'] is False or payload['kind'] == 'prepare'


# ------------------------------------------------------- journal: undo/redo ----

def test_a_created_table_can_be_undone_and_replayed():
    assert oracle.run('CREATE TABLE journal_demo (id NUMBER, note VARCHAR2(10))')['ok']
    assert 'JOURNAL_DEMO' in {table['name'] for table in oracle.catalogue()['tables']}

    undone = oracle.undo()
    assert undone['ok'], undone
    assert 'JOURNAL_DEMO' not in {table['name'] for table in undone['catalogue']['tables']}
    assert undone['journal']['can_redo'] is True

    replay = oracle.redo()
    assert replay['ok']
    assert 'JOURNAL_DEMO' in {table['name'] for table in replay['catalogue']['tables']}
    oracle.run('DROP TABLE journal_demo')


def test_an_insert_is_undone_row_by_row():
    oracle.run('CREATE TABLE journal_demo (id NUMBER, note VARCHAR2(10))')
    oracle.run("INSERT INTO journal_demo VALUES (1, 'first')")
    oracle.run("INSERT INTO journal_demo VALUES (2, 'second')")
    assert oracle.run('SELECT * FROM journal_demo')['row_count'] == 2

    assert oracle.undo()['ok']
    assert oracle.run('SELECT * FROM journal_demo')['row_count'] == 1
    assert oracle.undo()['ok']
    assert oracle.run('SELECT * FROM journal_demo')['row_count'] == 0
    oracle.run('DROP TABLE journal_demo')


def test_a_failed_statement_does_not_leave_a_snapshot():
    before = oracle.journal_state()['depth']
    assert oracle.run('INSERT INTO nowhere VALUES (1)')['ok'] is False
    assert oracle.journal_state()['depth'] == before


def test_a_read_never_touches_the_journal():
    before = oracle.journal_state()['depth']
    oracle.run('SELECT * FROM emp')
    assert oracle.journal_state()['depth'] == before


def test_nothing_to_undo_says_so():
    payload = oracle.undo()
    assert payload['ok'] is False and 'undo' in payload['error'].lower()


def test_reset_clears_the_journal():
    oracle.run('CREATE TABLE journal_demo (id NUMBER)')
    assert oracle.journal_state()['can_undo'] is True
    oracle.reset()
    assert oracle.journal_state()['can_undo'] is False
    assert oracle.journal_state()['can_redo'] is False


def test_a_new_change_clears_the_redo_stack():
    oracle.run('CREATE TABLE journal_demo (id NUMBER)')
    oracle.undo()
    assert oracle.journal_state()['can_redo'] is True
    oracle.run('CREATE TABLE journal_other (id NUMBER)')
    assert oracle.journal_state()['can_redo'] is False
    oracle.run('DROP TABLE journal_other')


# ------------------------------------------------------------------ routes ----

def test_the_journal_is_offered_by_the_tree_endpoint(admin):
    admin.post('/studio/oracle/run', json={'sql': 'CREATE TABLE http_demo (id NUMBER)'})
    tree = admin.get('/studio/oracle/tree').get_json()
    assert tree['journal']['can_undo'] is True
    assert 'CREATE TABLE http_demo' in tree['journal']['undo_label']
    admin.post('/studio/oracle/reset')


def test_undo_and_redo_over_http(admin):
    assert admin.post('/studio/oracle/run', json={'sql': 'CREATE TABLE http_demo (id NUMBER)'}).get_json()['ok']
    undone = admin.post('/studio/oracle/undo').get_json()
    assert undone['ok']
    assert 'HTTP_DEMO' not in {table['name'] for table in undone['catalogue']['tables']}
    replay = admin.post('/studio/oracle/redo').get_json()
    assert replay['ok']
    assert 'HTTP_DEMO' in {table['name'] for table in replay['catalogue']['tables']}
    admin.post('/studio/oracle/reset')


def test_the_journal_endpoints_are_administrator_only(faculty):
    for url in ('/studio/oracle/undo', '/studio/oracle/redo'):
        assert faculty.post(url).status_code in (302, 403)


def test_the_worksheet_offers_undo_and_redo(admin):
    body = admin.get('/studio').get_data(as_text=True)
    for marker in ('stUndoTool', 'stRedoTool', 'data-action="undo"', 'data-action="redo"',
                   'data-oracle-undo-url', 'data-oracle-redo-url', 'data-oracle-journal'):
        assert marker in body, marker
