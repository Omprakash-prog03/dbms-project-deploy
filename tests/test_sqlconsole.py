"""SQL console: run statements from the browser, safely."""
import pytest
from app import create_app
from repositories import rawdata, sqlconsole


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


def test_console_page_renders_for_administrators(admin):
    page = admin.get('/raw-data/query')
    assert page.status_code == 200
    body = page.data
    assert b'SQL console' in body
    assert b'sql-input' in body and b'Run statement' in body
    assert b'Allow a write without a WHERE clause' in body
    # The schema reference lists real tables and never a hash column value.
    assert b'department' in body and b'password_hash' in body
    assert b'$2b$' not in body


def test_non_administrators_cannot_open_the_console(faculty, student):
    for client in (faculty, student):
        assert client.get('/raw-data/query').status_code == 403
        assert client.post('/raw-data/query', data={'statement': 'SELECT 1'}).status_code == 403


def test_select_runs_and_prints_a_raw_grid(admin):
    response = admin.post('/raw-data/query', data={'statement': 'SELECT dept_code, dept_name FROM department;'})
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'rows returned' in body
    assert 'DEPT_CODE' in body and 'Computer Science' in body
    assert body.count('-') > 10


def test_insert_update_delete_really_change_data(admin):
    insert = sqlconsole.run("INSERT INTO department (dept_code, dept_name, established_year) "
                            "VALUES ('TST', 'Temporary Department', 2001)")
    assert insert['ok'] and insert['affected'] == 1
    assert insert['message'] == '1 row created.'
    created = rawdata.fetch('department')['total']

    found = sqlconsole.run("SELECT dept_code FROM department WHERE dept_code = 'TST'")
    assert found['ok'] and 'TST' in found['text']

    update = sqlconsole.run("UPDATE department SET dept_name = 'Renamed' WHERE dept_code = 'TST'")
    assert update['ok'] and update['message'] == '1 row updated.'
    assert 'Renamed' in sqlconsole.run("SELECT dept_name FROM department WHERE dept_code='TST'")['text']

    delete = sqlconsole.run("DELETE FROM department WHERE dept_code = 'TST'")
    assert delete['ok'] and delete['message'] == '1 row deleted.'
    assert rawdata.fetch('department')['total'] == created - 1


def test_writes_without_a_where_clause_need_confirmation():
    guarded = sqlconsole.run("UPDATE student SET status = 'Active'")
    assert guarded['ok'] is False and guarded['needs_confirmation'] is True
    assert 'no WHERE clause' in guarded['error']
    assert '320 rows' in guarded['error'] or 'rows)' in guarded['error']

    deleted = sqlconsole.run('DELETE FROM guardian')
    assert deleted['ok'] is False and deleted['needs_confirmation'] is True

    # With the explicit tick the statement is allowed to run. A self-assignment
    # proves the guard is released without touching the seeded data.
    total = rawdata.fetch('department')['total']
    allowed = sqlconsole.run('UPDATE department SET dept_code = dept_code', allow_full_write=True)
    assert allowed['ok'] is True
    assert allowed['affected'] == total
    assert allowed['message'] == f'{total:,} rows updated.'
    assert rawdata.fetch('department')['total'] == total


def test_schema_changes_are_refused():
    for statement in ('DROP TABLE department', 'ALTER TABLE student ADD COLUMN x INT',
                      'CREATE TABLE t (id INT)', 'TRUNCATE TABLE student',
                      'PRAGMA table_info(student)', 'BEGIN TRANSACTION'):
        outcome = sqlconsole.run(statement)
        assert outcome['ok'] is False, statement
        assert 'not allowed' in outcome['error']
    assert rawdata.fetch('department')['total'] >= 1


def test_dangerous_input_is_handled_cleanly():
    assert sqlconsole.run('')['error'].startswith('Type a statement first')
    assert sqlconsole.run('   ')['error'].startswith('Type a statement first')
    assert 'one statement at a time' in sqlconsole.run('SELECT 1; DROP TABLE student;')['error']
    assert 'not a statement' in sqlconsole.run('HELLO WORLD')['error']

    # A comment or a string containing a blocked keyword is not blocked by mistake.
    assert sqlconsole.run("SELECT 'DROP TABLE student' AS note")['ok'] is True
    assert sqlconsole.run('-- just a comment')['error'].startswith('That is only a comment')

    # Comments cannot hide a real DROP.
    assert 'not allowed' in sqlconsole.run('/* SELECT */ DROP TABLE student')['error']


def test_database_errors_are_reported_not_raised():
    outcome = sqlconsole.run("SELECT * FROM table_that_does_not_exist")
    assert outcome['ok'] is False
    assert 'no such table' in outcome['error'].lower() or 'doesn' in outcome['error'].lower()


def test_credentials_are_masked_in_results(admin):
    outcome = sqlconsole.run('SELECT * FROM app_user')
    assert outcome['ok'] is True
    assert 'password_hash' in outcome['columns']
    assert '$2b$' not in outcome['text']
    assert '•••' in outcome['text']

    page = admin.post('/raw-data/query', data={'statement': 'SELECT * FROM app_user'})
    assert b'$2b$' not in page.data
    # Writing a hash by hand is refused: bcrypt hashes come from the portal.
    blocked = sqlconsole.run("UPDATE app_user SET password_hash = 'x' WHERE user_id = 1")
    assert blocked['ok'] is False and 'bcrypt' in blocked['error']


def test_long_results_are_capped():
    outcome = sqlconsole.run('SELECT * FROM attendance')
    assert outcome['ok'] is True
    assert outcome['truncated'] > 0
    assert outcome['text'].count('\n') < 320


def test_history_is_remembered_per_session(admin):
    admin.post('/raw-data/query', data={'statement': 'SELECT 1 AS one'})
    page = admin.post('/raw-data/query', data={'statement': 'SELECT 2 AS two'})
    assert page.status_code == 200
    body = page.get_data(as_text=True)
    assert 'Statement history' in body
    assert 'SELECT 1 AS one' in body
    # Only the last few statements are kept.
    for index in range(12):
        admin.post('/raw-data/query', data={'statement': f'SELECT {index} AS n'})
    history = admin.get('/raw-data/query')
    assert history.status_code == 200
    with admin.session_transaction() as session:
        assert len(session['sql_history']) <= 8


def test_examples_and_schema_reference_match_the_database():
    names = set(rawdata.table_names())
    for example in sqlconsole.examples():
        assert example['label'] and example['sql']
        if 'FROM' in example['sql'].upper():
            target = sqlconsole._table_of(example['sql'])
            assert target in names, target
    for table in sqlconsole.schema_reference():
        assert table['name'] in names
        assert table['columns']
        assert all(column['name'] not in rawdata.HIDDEN_COLUMNS for column in table['columns'])


def test_raw_data_page_links_to_the_console(admin):
    page = admin.get('/raw-data?table=student')
    assert b'/raw-data/query' in page.data
