"""SQL console: run statements against the live database from the browser.

Administrator only. Read statements are unlimited; data changes (INSERT,
UPDATE, DELETE) are committed immediately. Schema changes are refused so the
portal cannot be broken from a text box, and credential columns stay hidden.
"""
import re
import time
from decimal import Decimal

from repositories import rawdata
from repositories.db_pool import db_pool

READ_VERBS = {'SELECT', 'WITH', 'SHOW', 'DESCRIBE', 'DESC', 'EXPLAIN', 'TABLE', 'VALUES'}
WRITE_VERBS = {'INSERT', 'REPLACE', 'UPDATE', 'DELETE'}
BLOCKED_VERBS = {'DROP', 'ALTER', 'CREATE', 'TRUNCATE', 'RENAME', 'ATTACH', 'DETACH',
                 'PRAGMA', 'VACUUM', 'REINDEX', 'ANALYZE', 'GRANT', 'REVOKE', 'BEGIN',
                 'COMMIT', 'ROLLBACK', 'SAVEPOINT', 'SET', 'USE', 'CALL', 'LOAD', 'DO'}
MAX_ROWS = 200
MAX_CELL = 40
HISTORY_LIMIT = 8
_PLACEHOLDER = '•••'


def _strip_noise(statement):
    """Remove comments and quoted text so keyword checks cannot be fooled."""
    text = re.sub(r'/\*.*?\*/', ' ', statement, flags=re.S)
    text = re.sub(r'--[^\n]*', ' ', text)
    text = re.sub(r'#[^\n]*', ' ', text)
    text = re.sub(r"'(?:''|[^'])*'", "''", text)
    text = re.sub(r'"(?:""|[^"])*"', '""', text)
    return text


def clean(statement):
    """The statement without its trailing semicolon, or an error string."""
    text = (statement or '').strip()
    if not text:
        return '', 'Type a statement first, for example: SELECT * FROM department;'
    stripped = _strip_noise(text).strip()
    if ';' in stripped.rstrip(';').strip():
        return '', 'Run one statement at a time. Remove everything after the first semicolon.'
    if not stripped.rstrip(';').strip():
        return '', 'That is only a comment. Add a statement to run.'
    return text.rstrip().rstrip(';').strip(), ''


def _verb(statement):
    cleaned = _strip_noise(statement).strip().lstrip('( ').split()
    return cleaned[0].upper() if cleaned else ''


def _is_numeric(values):
    for value in values:
        if value is None:
            continue
        return isinstance(value, (int, float, Decimal)) and not isinstance(value, bool)
    return False


def _cell(value):
    if value is None:
        return 'NULL'
    if isinstance(value, Decimal):
        return f'{value:,}' if value == value.to_integral_value() else f'{value:,.2f}'
    if isinstance(value, float):
        return f'{value:,}'
    text = str(value)
    return text if len(text) <= MAX_CELL else text[:MAX_CELL - 1] + '…'


def run(statement, allow_full_write=False):
    """Execute one statement and return everything the page needs to report it."""
    sql, error = clean(statement)
    if error:
        return {'ok': False, 'error': error, 'statement': statement}

    verb = _verb(sql)
    lowered = _strip_noise(sql).lower()

    if verb in BLOCKED_VERBS:
        return {'ok': False, 'statement': sql, 'error': (
            f'{verb} is not allowed in the SQL console. Schema changes and transaction '
            'control would let a typo break the portal; use the management screens for '
            'structure, and run data changes (INSERT, UPDATE, DELETE) here.')}
    if verb not in READ_VERBS | WRITE_VERBS:
        return {'ok': False, 'statement': sql, 'error': (
            f'“{verb or "?"}” is not a statement this console runs. Allowed: '
            'SELECT, WITH, INSERT, UPDATE, DELETE (and SHOW/DESCRIBE/EXPLAIN on MySQL).')}

    writing = verb in WRITE_VERBS
    if writing and ('login_history' in lowered or 'staff_activity' in lowered):
        return {'ok': False, 'statement': sql, 'error': (
            'The sign-in history and the change log are append-only: they cannot be '
            'inserted into, changed or deleted, not even here. The portal writes to them '
            'by itself on every sign-in, sign-out and data change.')}

    if writing and 'password_hash' in lowered:
        return {'ok': False, 'statement': sql, 'error': (
            'password_hash must be a bcrypt hash, so it cannot be set from SQL. Create the '
            'account in the portal, or run: python scripts/reset_password.py --username <name> '
            '--password <new password>')}

    if writing and verb in ('UPDATE', 'DELETE') and not re.search(r'\bwhere\b', lowered):
        if not allow_full_write:
            table = _table_of(sql)
            count = rawdata.row_count(table) if table in rawdata.table_names() else 0
            return {'ok': False, 'statement': sql, 'needs_confirmation': True, 'error': (
                f'This {verb} has no WHERE clause, so it would touch every row of '
                f'{table or "the table"} ({count:,} rows).')}

    started = time.perf_counter()
    try:
        if writing:
            result = db_pool.execute_dml(sql)
            elapsed = (time.perf_counter() - started) * 1000
            rows = result.get('rowcount')
            rows = 0 if rows is None or rows < 0 else rows
            past = {'INSERT': 'created', 'REPLACE': 'created', 'UPDATE': 'updated'}.get(verb, 'deleted')
            message = f'{rows:,} row{"" if rows == 1 else "s"} {past}.'
            return {
                'ok': True, 'statement': sql, 'kind': 'write', 'verb': verb,
                'elapsed': round(elapsed, 1), 'affected': rows, 'message': message,
                'text': f'{message}\nChanges are committed.',
            }

        payload = db_pool.execute_query(sql, fetch='table')
        elapsed = (time.perf_counter() - started) * 1000
        columns = list(payload['columns'])
        records = payload['rows'] or []
        values = [[row[column] for column in columns] for row in records]
        numeric = [_is_numeric([row[position] for row in values]) for position in range(len(columns))]
        masked = []
        for row, record in enumerate(values):
            masked.append([
                _PLACEHOLDER if columns[position] in rawdata.HIDDEN_COLUMNS else _cell(record[position])
                for position in range(len(columns))
            ])
        shown = masked[:MAX_ROWS]
        widths = []
        for position, column in enumerate(columns):
            longest = max([len(column)] + [len(row[position]) for row in shown] or [0])
            widths.append(max(4, min(longest, MAX_CELL)))
        return {
            'ok': True, 'statement': sql, 'kind': 'read', 'verb': verb,
            'elapsed': round(elapsed, 1), 'columns': columns,
            'truncated': len(masked) - len(shown),
            'message': (f'{len(masked):,} row{"" if len(masked) == 1 else "s"} returned.'),
            'text': rawdata.grid_text(columns, numeric, widths, shown,
                                      empty_message='Statement completed: no rows returned.'),
        }
    except Exception as exc:  # The database's own message is the most useful feedback.
        elapsed = (time.perf_counter() - started) * 1000
        return {'ok': False, 'statement': sql, 'elapsed': round(elapsed, 1),
                'error': str(exc).strip() or 'The database rejected that statement.'}


def _table_of(sql):
    match = re.search(r'\b(?:update|delete\s+from|from|into)\s+"?([A-Za-z_][A-Za-z0-9_]*)"?',
                      _strip_noise(sql), re.I)
    return match.group(1) if match else ''


def remember(session, outcome):
    """Keep the last few statements so the console has a usable history."""
    entry = {
        'statement': outcome.get('statement', ''),
        'ok': bool(outcome.get('ok')),
        'summary': (outcome.get('message') or outcome.get('error') or '')[:160],
    }
    history = [item for item in session.get('sql_history', []) if item['statement'] != entry['statement']]
    session['sql_history'] = ([entry] + history)[:HISTORY_LIMIT]


def examples():
    """Statements that actually fit this schema, ready to edit and run."""
    return [
        {'label': 'Add a department', 'sql': (
            "INSERT INTO department (dept_code, dept_name, hod_faculty_id, established_year)\n"
            "VALUES ('CSE', 'Computer Science & Engineering', NULL, 2001);")},
        {'label': 'Add a course', 'sql': (
            "INSERT INTO course (course_code, title, dept_id, credits, semester_no)\n"
            "VALUES ('CS301', 'Database Management Systems', 1, 4, 3);")},
        {'label': 'Add a student', 'sql': (
            "INSERT INTO student (roll_no, first_name, last_name, email, phone, dob, gender,\n"
            "                     address, dept_id, admission_date, current_semester, status)\n"
            "VALUES ('26CSE001', 'Aarav', 'Sharma', 'aarav@nist.edu', '9876500001', '2005-04-12',\n"
            "        'Male', 'Bhubaneswar', 1, '2026-06-10', 1, 'Active');")},
        {'label': 'Update a status', 'sql': (
            "UPDATE student\nSET status = 'Graduated'\nWHERE roll_no = '26CSE001';")},
        {'label': 'Check the result', 'sql': "SELECT * FROM student ORDER BY student_id DESC;"},
    ]


def schema_reference():
    """Columns per table, so statements can be written without guessing."""
    names = rawdata.table_names()
    known = set(names)
    return [{'name': name, 'rows': rawdata.row_count(name),
             'columns': rawdata.columns(name, known=known)} for name in names]
