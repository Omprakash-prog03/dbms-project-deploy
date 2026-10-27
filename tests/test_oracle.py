"""The Oracle practice connection inside SQL Studio.

The second connection accepts Oracle SQL and *runs* it: tables are created,
rows are inserted and dropped again, sequences advance, and errors arrive with
Oracle codes. The portal's own tables are never touched. These tests hold the
connection to that promise, and check the screen offers it.
"""
import json

import pytest

from app import create_app
from repositories import oracle


@pytest.fixture(autouse=True)
def practice(tmp_path, monkeypatch):
    """Every test gets its own practice schema, seeded like a fresh install."""
    monkeypatch.setenv('STUDIO_ORACLE_PATH', str(tmp_path / 'practice.db'))
    oracle.reset()
    yield
    for name in ('SCRATCH', 'SCRATCH2', 'T1', 'T2', 'V_SCRATCH'):
        oracle.run(f'DROP TABLE {name}', seeding=True)
        oracle.run(f'DROP VIEW {name}', seeding=True)


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


# ------------------------------------------------------------- the schema ----

def test_the_practice_schema_arrives_with_the_scott_demonstration():
    catalogue = oracle.catalogue()
    tables = {table['name']: table for table in catalogue['tables']}
    assert {'EMP', 'DEPT'} <= set(tables)
    assert tables['EMP']['rows'] == 14
    assert tables['DEPT']['rows'] == 4
    assert any(column['name'] == 'EMPNO' and column['pk'] for column in tables['EMP']['columns'])
    assert any(index['name'] == 'EMP_DEPTNO_IDX' for index in catalogue['indexes'])
    assert any(sequence['name'] == 'EMP_SEQ' for sequence in catalogue['sequences'])


def test_the_connection_announces_itself_as_oracle_and_as_a_simulation():
    connection = oracle.connection()
    assert connection['name'] == 'ORACLE_XE'
    assert connection['user'] == 'STUDIO'
    assert 'Oracle' in connection['product']
    assert connection['kind'] == 'simulated'


def test_the_practice_file_is_never_the_portal_database(monkeypatch):
    import os
    from config import BASE_DIR, Config
    monkeypatch.setenv('STUDIO_ORACLE_PATH', Config.SQLITE_PATH)
    portal = os.path.abspath(os.path.join(str(BASE_DIR), Config.SQLITE_PATH))
    assert oracle.path() != portal


# ---------------------------------------------------------------- reading ----

def test_a_read_returns_oracle_named_columns():
    payload = oracle.run('SELECT empno, ename, sal FROM emp WHERE rownum <= 3')
    assert payload['ok'] and payload['kind'] == 'read'
    assert [column['name'] for column in payload['columns']] == ['EMPNO', 'ENAME', 'SAL']
    assert payload['row_count'] == 3
    assert payload['rows'][0]['cells'][1]['text']


def test_the_oracle_functions_are_translated_and_noted():
    payload = oracle.run("SELECT USER, SYSDATE, NVL(comm, 0) AS paid, DECODE(deptno, 10, 'A', 'B') AS band FROM emp WHERE rownum <= 1")
    assert payload['ok'], payload['error']
    assert [column['name'] for column in payload['columns']] == ['USER', 'SYSDATE', 'PAID', 'BAND']
    assert payload['rows'][0]['cells'][0]['text'] == 'STUDIO'
    assert payload['translated'] and 'dual' not in payload['translated'].lower()
    assert 'IFNULL' in payload['translated'].upper()
    assert 'CASE' in payload['translated'].upper()


def test_dual_carries_the_environment_functions():
    payload = oracle.run('SELECT 1 + 1 AS answer FROM dual')
    assert payload['ok']
    assert payload['rows'][0]['cells'][0]['text'] == '2'


def test_group_concat_within_group_keeps_the_order():
    payload = oracle.run(
        "SELECT deptno, LISTAGG(ename, ', ') WITHIN GROUP (ORDER BY ename) AS names "
        "FROM emp WHERE deptno = 10 GROUP BY deptno")
    assert payload['ok'], payload['error']
    assert payload['rows'][0]['cells'][1]['text'] == 'CLARK, KING, MILLER'


def test_fetch_first_and_offset_are_understood():
    first = oracle.run('SELECT empno FROM emp ORDER BY empno FETCH FIRST 2 ROWS ONLY')
    assert first['ok'] and first['row_count'] == 2
    second = oracle.run('SELECT empno FROM emp ORDER BY empno OFFSET 12 ROWS FETCH NEXT 2 ROWS ONLY')
    assert second['ok'] and second['row_count'] == 2


# --------------------------------------------------------------- writing ----

def test_a_table_can_be_created_filled_and_read_back():
    created = oracle.run('CREATE TABLE scratch (id NUMBER(6) GENERATED BY DEFAULT AS IDENTITY, '
                         'note VARCHAR2(20) NOT NULL)')
    assert created['ok'] and created['kind'] == 'ddl'
    assert created['message'] == 'Table created.'
    assert 'AUTOINCREMENT' in created['translated']

    assert oracle.run("INSERT INTO scratch (note) VALUES ('first')")['message'] == '1 row created.'
    assert oracle.run("INSERT INTO scratch (note) VALUES ('second')")['message'] == '1 row created.'

    rows = oracle.run('SELECT id, note FROM scratch ORDER BY id')['rows']
    assert [[cell['text'] for cell in row['cells']] for row in rows] == [['1', 'first'], ['2', 'second']]

    updated = oracle.run("UPDATE scratch SET note = 'changed' WHERE id = 2")
    assert updated['ok'] and updated['message'] == '1 row updated.'

    removed = oracle.run('DELETE FROM scratch WHERE id = 1')
    assert removed['ok'] and removed['message'] == '1 row deleted.'

    dropped = oracle.run('DROP TABLE scratch')
    assert dropped['ok'] and dropped['message'] == 'Table dropped.'
    missing = oracle.run('SELECT * FROM scratch')
    assert not missing['ok'] and missing['code'] == 'ORA-00942'


def test_a_view_and_an_index_can_be_created():
    assert oracle.run('CREATE VIEW v_scratch AS SELECT empno, ename FROM emp WHERE deptno = 10')['ok']
    view = oracle.run('SELECT ename FROM v_scratch')
    assert view['ok'] and view['row_count'] == 3
    assert oracle.run('CREATE INDEX scratch_idx ON emp (sal)')['ok']
    assert oracle.run('DROP VIEW v_scratch')['ok']


def test_a_sequence_advances_the_way_oracle_does():
    created = oracle.run('CREATE SEQUENCE scratch_seq START WITH 100 INCREMENT BY 10')
    assert created['ok']
    # Oracle's first NEXTVAL after START WITH 100 is 100, not 110
    assert oracle.run('SELECT scratch_seq.NEXTVAL FROM dual')['rows'][0]['cells'][0]['text'] == '100'
    assert oracle.run('SELECT scratch_seq.NEXTVAL FROM dual')['rows'][0]['cells'][0]['text'] == '110'
    assert oracle.run('SELECT scratch_seq.CURRVAL FROM dual')['rows'][0]['cells'][0]['text'] == '110'
    assert oracle.run('DROP SEQUENCE scratch_seq')['ok']


def test_describe_prints_the_oracle_types():
    payload = oracle.run('DESCRIBE emp')
    assert payload['ok'] and payload['kind'] == 'describe'
    assert [column['name'] for column in payload['columns']] == ['Name', 'Null?', 'Type']
    first = [cell['text'] for cell in payload['rows'][0]['cells']]
    assert first[0] == 'EMPNO' and first[2].startswith('NUMBER')


def test_explain_plan_for_returns_steps():
    payload = oracle.run('EXPLAIN PLAN FOR SELECT * FROM emp WHERE deptno = 10')
    assert payload['ok'] and payload['kind'] == 'plan'
    assert payload['nodes']


# ---------------------------------------------------------------- errors ----

def test_an_unknown_table_is_ora_00942():
    payload = oracle.run('SELECT * FROM nowhere')
    assert not payload['ok']
    assert payload['code'] == 'ORA-00942'
    assert 'table or view does not exist' in payload['error']


def test_an_unknown_column_is_ora_00904():
    payload = oracle.run('SELECT no_such_column FROM emp')
    assert payload['code'] == 'ORA-00904'
    assert 'invalid identifier' in payload['error']


def test_a_missing_not_null_value_is_ora_01400():
    oracle.run('CREATE TABLE scratch2 (id NUMBER, note VARCHAR2(10) NOT NULL)')
    payload = oracle.run('INSERT INTO scratch2 (id) VALUES (1)')
    assert payload['code'] == 'ORA-01400'
    assert 'cannot insert NULL' in payload['error']


def test_a_duplicate_key_is_ora_00001():
    payload = oracle.run("INSERT INTO dept (deptno, dname) VALUES (10, 'DUPLICATE')")
    assert payload['code'] == 'ORA-00001'


def test_plsql_blocks_are_refused_with_a_pointer_to_the_workshop():
    payload = oracle.run('BEGIN NULL; END;')
    assert not payload['ok'] and payload['code'] == 'ORA-00933'
    assert 'PL/SQL' in payload['error']
    assert 'workshop' in payload['hint'].lower() or 'db/' in payload['hint']


def test_connect_by_is_refused_rather_than_silently_wrong():
    payload = oracle.run('SELECT LEVEL FROM emp CONNECT BY PRIOR empno = mgr')
    assert not payload['ok'] and payload['code'] == 'ORA-00933'


# --------------------------------------------------------------- scripts ----

def test_a_script_reports_every_statement():
    payload = oracle.run_script(
        'CREATE TABLE scratch2 (id NUMBER, note VARCHAR2(10));\n'
        "INSERT INTO scratch2 VALUES (1, 'a');\n"
        'SELECT * FROM scratch2;\n'
        'DROP TABLE scratch2;')
    assert payload['ok']
    assert payload['total'] == 4 and payload['succeeded'] == 4 and not payload['failed']
    assert [statement['verb'] for statement in payload['statements']] == \
        ['CREATE', 'INSERT', 'SELECT', 'DROP']


def test_a_script_keeps_going_after_a_bad_statement():
    payload = oracle.run_script('SELECT * FROM nowhere;\nSELECT 1 FROM dual;')
    assert payload['total'] == 2 and payload['succeeded'] == 1 and payload['failed'] == 1
    assert payload['statements'][0]['code'] == 'ORA-00942'
    assert payload['statements'][1]['ok']


def test_the_starter_script_runs_every_statement():
    payload = oracle.run_script(oracle.STARTER)
    assert payload['ok'], [statement for statement in payload['statements'] if not statement['ok']]
    assert payload['total'] == 10 and payload['succeeded'] == 10
    table = oracle.run('SELECT title, budget FROM project ORDER BY project_id')
    assert table['ok'] and table['row_count'] == 2
    assert oracle.run('DESCRIBE project')['ok']


def test_a_comment_above_a_statement_is_not_part_of_it():
    payload = oracle.run('-- a note the reader needs\n-- and a second line\nSELECT 1 FROM dual')
    assert payload['ok'], payload.get('error')
    assert payload['rows'][0]['cells'][0]['text'] == '1'


# ----------------------------------------------------------------- reset ----

def test_reset_puts_the_scott_schema_back():
    oracle.run('CREATE TABLE scratch (id NUMBER)')
    assert any(table['name'] == 'SCRATCH' for table in oracle.catalogue()['tables'])
    payload = oracle.reset()
    assert payload['ok'] and payload['tables'] == 2
    assert [table['name'] for table in oracle.catalogue()['tables']] == ['DEPT', 'EMP']


# ----------------------------------------------------------------- routes ----

def test_an_administrator_can_run_a_statement_over_http(admin):
    payload = admin.post('/studio/oracle/run', json={'sql': 'SELECT ename FROM emp WHERE deptno = 30'}).get_json()
    assert payload['ok'] and payload['row_count'] == 6


def test_the_tree_reflects_a_table_created_over_http(admin):
    assert admin.post('/studio/oracle/run', json={'sql': 'CREATE TABLE scratch3 (id NUMBER)'}).get_json()['ok']
    tree = admin.get('/studio/oracle/tree').get_json()
    assert 'ok' in tree
    names = [table['name'] for table in tree['catalogue']['tables']]
    assert 'SCRATCH3' in names
    admin.post('/studio/oracle/reset')


def test_every_oracle_endpoint_refuses_a_non_administrator(faculty, student):
    for client in (faculty, student):
        for url in ('/studio/oracle/run', '/studio/oracle/script', '/studio/oracle/explain',
                    '/studio/oracle/reset'):
            assert client.post(url, json={'sql': 'SELECT 1 FROM dual'}).status_code in (302, 403), url
        assert client.get('/studio/oracle/tree').status_code in (302, 403)


def test_the_studio_screen_offers_both_connections(admin):
    page = admin.get('/studio')
    body = page.get_data(as_text=True)
    for marker in ('ORACLE_XE', 'stConnectionSelect', 'stTreeOracle', 'stOracleTables',
                   'stOracleSequences', 'stCommand', 'stOracleDialog', 'oracle-reset',
                   'data-oracle-run-url', 'Oracle practice schema'):
        assert marker in body, marker
    assert '{{' not in body


def test_the_portal_connection_now_writes_and_undoes(admin):
    """v10: the studio's portal connection is live, and one undo takes it back."""
    from repositories import studio
    studio.portal_journal().clear()
    before = admin.get('/database').status_code
    payload = admin.post('/studio/run', json={
        'sql': "UPDATE student SET status = 'Suspended' WHERE student_id = 2"}).get_json()
    assert payload['ok'] is True, payload
    assert payload['kind'] == 'write'
    assert payload['journal']['can_undo'] is True
    undone = admin.post('/studio/undo', json={}).get_json()
    assert undone['ok'] is True
    studio.portal_journal().clear()
    assert before == 200


def test_a_missing_sql_body_is_a_client_error(admin):
    response = admin.post('/studio/oracle/run', json={})
    assert response.status_code == 400
    assert response.get_json()['ok'] is False


def test_the_response_is_json_and_round_trips(admin):
    response = admin.post('/studio/oracle/run', json={'sql': 'SELECT USER FROM dual'})
    assert response.mimetype == 'application/json'
    assert json.loads(response.get_data(as_text=True))['rows'][0]['cells'][0]['text'] == 'STUDIO'
