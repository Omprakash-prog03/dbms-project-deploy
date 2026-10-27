"""SQL Studio: a read-only simulation of a desktop database client.

The portal's workshop explains the schema; this module gives the administrator a
client to *use* it with — the navigator, the worksheet, the result grid, the
script output and the execution plan, all driven by the running database.

One rule shapes everything here: the studio never changes a row. A read
statement is executed. A data-changing statement is *prepared* by the engine
(`EXPLAIN` compiles it without running it) so the client can report that the
statement is valid, and then declines to commit. Structure changes, transaction
control and engine settings are refused outright.
"""
import re
import time
from decimal import Decimal

from repositories import rawdata
from repositories import workshop
from repositories.db_pool import db_pool

MAX_ROWS = 300
_QUOTE = '`' if workshop.is_mysql() else '"'
MAX_CELL = 120
CONNECTION_NAME = 'NIST_UNIVERSITY'

READ_VERBS = {'SELECT', 'WITH', 'VALUES', 'TABLE', 'SHOW', 'DESCRIBE', 'DESC'}
WRITE_VERBS = {'INSERT', 'REPLACE', 'UPDATE', 'DELETE', 'MERGE'}
BLOCKED_VERBS = {'DROP', 'ALTER', 'CREATE', 'TRUNCATE', 'RENAME', 'ATTACH', 'DETACH',
                 'PRAGMA', 'VACUUM', 'REINDEX', 'ANALYZE', 'GRANT', 'REVOKE', 'BEGIN',
                 'COMMIT', 'ROLLBACK', 'SAVEPOINT', 'RELEASE', 'SET', 'USE', 'CALL',
                 'EXEC', 'EXECUTE', 'LOAD', 'DO', 'LOCK', 'UNLOCK'}
PLACEHOLDER = '•••'

_READ_ONLY_NOTE = ('SQL Studio is a read-only session: the statement was prepared and '
                   'validated by the engine, but nothing was written or committed.')
_WRITE_VERBS_TEXT = ', '.join(sorted(WRITE_VERBS))


# ---------------------------------------------------------------------------
# the connection and the navigator
# ---------------------------------------------------------------------------
def connection():
    """Everything the title bar, the status bar and the About dialog show."""
    facts = workshop.storage()
    counts = workshop.overview()['counts']
    return {
        'name': CONNECTION_NAME,
        'engine': facts.get('engine', ''),
        'version': facts.get('version', ''),
        'database': facts.get('database', ''),
        'size': facts.get('size', ''),
        'page_size': facts.get('page_size', ''),
        'journal': facts.get('journal', ''),
        'foreign_keys': facts.get('foreign_keys', 'ON'),
        'read_only': True,
        'autocommit': 'OFF (simulated)',
        'isolation': 'SERIALIZABLE (SQLite default)',
        'schema': 'main',
        'charset': 'UTF-8',
        'counts': counts,
    }


def _table_row_count(table):
    try:
        return int(db_pool.execute_query(
            f'SELECT COUNT(*) AS n FROM {_QUOTE}{table}{_QUOTE}', fetch='one').get('n') or 0)
    except Exception:
        return 0


def catalogue():
    """The object tree: tables with their columns, views, indexes, rules, code."""
    tables = []
    for table in workshop.tables():
        columns = workshop.columns(table)
        tables.append({
            'name': table,
            'rows': _table_row_count(table),
            'columns': [{'name': column['name'], 'type': column['type'] or '—',
                         'pk': bool(column['pk']), 'nullable': column['nullable'],
                         'default': column['default'] if column['default'] is not None else ''}
                        for column in columns],
            'foreign_keys': workshop.foreign_keys(table),
        })
    views = [{'name': view['name'],
              'columns': [{'name': column['name'], 'type': column['type'] or '—'}
                          for column in workshop.columns(view['name'])],
              'purpose': view.get('purpose', ''),
              'rows': _table_row_count(view['name'])}
             for view in workshop.views()]
    indexes = [{'name': index['name'], 'table': index['table'],
                'columns': index['columns'], 'unique': index['unique']}
               for index in workshop.indexes()]
    triggers = [{'name': trigger['name'], 'table': trigger['table'],
                 'timing': trigger['timing'], 'event': trigger['event'],
                 'message': trigger.get('message', '')}
                for trigger in workshop.triggers()]
    procedures = [{'name': item['name'], 'params': item['params'],
                   'purpose': item.get('purpose', '')}
                  for item in workshop.procedures()]
    functions = [{'name': item['name'], 'params': item['params'],
                  'returns': item.get('returns', ''), 'purpose': item.get('purpose', '')}
                 for item in workshop.functions()]
    return {'tables': tables, 'views': views, 'indexes': indexes, 'triggers': triggers,
            'procedures': procedures, 'functions': functions}


def snippets():
    """The starter script and the snippet list in the Tools menu."""
    return [
        {'label': 'Every student, newest first',
         'sql': 'SELECT student_id, roll_no, first_name, last_name, status\n'
                'FROM student\nORDER BY student_id DESC\nLIMIT 50;'},
        {'label': 'Enrolments with the course they belong to',
         'sql': 'SELECT e.enrollment_id, s.roll_no, c.course_code, c.title, co.term, e.status\n'
                'FROM enrollment e\n'
                'JOIN student s ON s.student_id = e.student_id\n'
                'JOIN course_offering co ON co.offering_id = e.offering_id\n'
                'JOIN course c ON c.course_id = co.course_id\n'
                'ORDER BY e.enrollment_id DESC\nLIMIT 50;'},
        {'label': 'Attendance percentage per enrolment',
         'sql': "SELECT a.enrollment_id,\n"
                "       COUNT(*) AS classes,\n"
                "       SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) AS present,\n"
                "       ROUND(100.0 * SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END)\n"
                "             / COUNT(*), 2) AS percentage\n"
                "FROM attendance a\nGROUP BY a.enrollment_id\nORDER BY percentage DESC\nLIMIT 50;"},
        {'label': 'Fee balance per student',
         'sql': 'SELECT s.roll_no,\n'
                '       SUM(f.amount) AS billed,\n'
                '       COALESCE((SELECT SUM(p.amount_paid) FROM fee_payment p\n'
                '                 WHERE p.student_id = s.student_id), 0) AS paid\n'
                'FROM student s\n'
                'JOIN fee_structure f ON f.dept_id = s.dept_id AND f.semester_no = s.current_semester\n'
                'GROUP BY s.student_id, s.roll_no\nORDER BY billed DESC\nLIMIT 50;'},
        {'label': 'Describe a table',
         'sql': 'SELECT name, type, "notnull" AS required, pk\n'
                'FROM pragma_table_info(\'student\');'},
        {'label': 'Check the query plan',
         'sql': 'EXPLAIN QUERY PLAN\n'
                'SELECT s.roll_no, c.course_code\n'
                'FROM enrollment e\n'
                'JOIN student s ON s.student_id = e.student_id\n'
                'JOIN course_offering co ON co.offering_id = e.offering_id\n'
                'JOIN course c ON c.course_id = co.course_id\n'
                'WHERE e.status = \'Enrolled\';'},
    ]


def starter_script():
    """What the first worksheet opens with — a script that reads well out loud."""
    return """-- ============================================================================
-- NIST University · SQL Studio
-- A read-only session against the live portal database.
--
--   F9 / Ctrl+Enter   run the statement under the cursor
--   F5                run the whole script, one statement at a time
--   F10               show the execution plan
--
-- Nothing typed here can change a row: SELECT statements run for real, data
-- changes are compiled and then declined, and schema changes are refused.
-- ============================================================================

-- 1. The catalogue this session is connected to.
SELECT name, type
FROM sqlite_master
WHERE type IN ('table', 'view')
ORDER BY type, name;

-- 2. Students, with the department they belong to.
SELECT s.roll_no, s.first_name || ' ' || s.last_name AS student,
       d.dept_code, s.current_semester, s.status
FROM student s
JOIN department d ON d.dept_id = s.dept_id
ORDER BY s.roll_no
LIMIT 25;

-- 3. How many enrolments each course offering carries.
SELECT c.course_code, c.title, co.term, co.capacity, co.enrolled_count,
       COUNT(e.enrollment_id) AS enrolled
FROM course_offering co
JOIN course c ON c.course_id = co.course_id
LEFT JOIN enrollment e ON e.offering_id = co.offering_id
GROUP BY co.offering_id, c.course_code, c.title, co.term, co.capacity, co.enrolled_count
ORDER BY enrolled DESC
LIMIT 15;

-- 4. The same statement, planned. Press F10 on it to see the operators.
EXPLAIN QUERY PLAN
SELECT s.roll_no, COUNT(e.enrollment_id) AS courses
FROM student s
LEFT JOIN enrollment e ON e.student_id = s.student_id
GROUP BY s.student_id
ORDER BY courses DESC
LIMIT 10;
"""


# ---------------------------------------------------------------------------
# statement handling
# ---------------------------------------------------------------------------
def _strip_noise(text):
    """Blank out comments and string literals so keyword checks cannot be fooled."""
    text = re.sub(r'/\*.*?\*/', ' ', text, flags=re.S)
    text = re.sub(r'--[^\n]*', ' ', text)
    text = re.sub(r'#[^\n]*', ' ', text)
    text = re.sub(r"'(?:''|[^'])*'", "''", text)
    text = re.sub(r'"(?:""|[^"])*"', '""', text)
    return text


def classify(sql):
    """read / write / blocked / unknown — decided on comment-stripped text."""
    words = _strip_noise(sql).strip().lstrip('( ').split()
    verb = words[0].upper() if words else ''
    if verb in READ_VERBS:
        return verb, 'read'
    if verb == 'EXPLAIN':
        return verb, 'read'
    if verb in WRITE_VERBS:
        return verb, 'write'
    if verb in BLOCKED_VERBS:
        return verb, 'blocked'
    return verb, 'unknown'


def clean(sql):
    """One statement, without its trailing semicolon or SQL*Plus slash."""
    text = (sql or '').strip()
    if text.endswith('/') and not text.endswith('*/'):
        text = text[:-1].rstrip()
    body = _strip_noise(text).strip().rstrip(';').strip()
    if not body:
        return '', 'Nothing to run: the editor is empty, or holds only comments.'
    if ';' in body:
        return '', ('That is more than one statement. Press F5 to run a script, or '
                    'Ctrl+Enter to run the statement under the cursor.')
    return text.rstrip().rstrip(';').rstrip(), ''


def split_script(text):
    """Split a worksheet into statements, respecting quotes, comments and BEGIN…END."""
    statements = []
    buffer = []
    index = 0
    length = len(text or '')
    quote = ''
    line_comment = False
    block_comment = False
    depth = 0
    start = 0
    while index < length:
        char = text[index]
        pair = text[index:index + 2]
        if line_comment:
            buffer.append(char)
            if char == '\n':
                line_comment = False
            index += 1
            continue
        if block_comment:
            buffer.append(char)
            if pair == '*/':
                buffer.append('/')
                index += 2
                block_comment = False
                continue
            index += 1
            continue
        if quote:
            buffer.append(char)
            if char == quote:
                if text[index:index + 2] == quote * 2:
                    buffer.append(quote)
                    index += 2
                    continue
                quote = ''
            index += 1
            continue
        if pair == '--':
            buffer.append(pair)
            index += 2
            line_comment = True
            continue
        if pair == '/*':
            buffer.append(pair)
            index += 2
            block_comment = True
            continue
        if char in ('\'', '"', '`'):
            quote = char
            buffer.append(char)
            index += 1
            continue
        if char == ';':
            statement = ''.join(buffer).strip()
            if _strip_noise(statement).strip():
                statements.append({'sql': statement, 'offset': start})
            buffer = []
            index += 1
            start = index
            continue
        buffer.append(char)
        index += 1
    tail = ''.join(buffer).strip()
    if _strip_noise(tail).strip():
        statements.append({'sql': tail, 'offset': start})
    return statements


def _numeric(values):
    for value in values:
        if value is None:
            continue
        return isinstance(value, (int, float, Decimal)) and not isinstance(value, bool)
    return False


def _cell(value):
    if value is None:
        return {'text': 'NULL', 'null': True, 'numeric': False}
    if isinstance(value, bool):
        return {'text': 'true' if value else 'false', 'null': False, 'numeric': False}
    if isinstance(value, Decimal):
        text = f'{value:,}' if value == value.to_integral_value() else f'{value:,.2f}'
        return {'text': text, 'null': False, 'numeric': True}
    if isinstance(value, (int, float)):
        return {'text': f'{value:,}', 'null': False, 'numeric': True}
    text = str(value)
    return {'text': text if len(text) <= MAX_CELL else text[:MAX_CELL - 1] + '…',
            'null': False, 'numeric': False}


def _grid(cursor_rows, columns, elapsed):
    values = [[row[column] for column in columns] for row in cursor_rows]
    numeric = [False if column in rawdata.HIDDEN_COLUMNS
               else _numeric([row[position] for row in values])
               for position, column in enumerate(columns)]
    hidden = {'text': PLACEHOLDER, 'null': False, 'numeric': False}
    masked = [[hidden if column in rawdata.HIDDEN_COLUMNS else _cell(value)
               for column, value in zip(columns, row)] for row in values]
    shown = masked[:MAX_ROWS]
    return {
        'columns': [{'name': column, 'numeric': numeric[position]}
                    for position, column in enumerate(columns)],
        'rows': [{'number': number, 'cells': row}
                 for number, row in enumerate(shown, start=1)],
        'row_count': len(masked),
        'shown': len(shown),
        'truncated': len(masked) - len(shown),
        'elapsed_ms': elapsed,
    }


def run(sql):
    """Execute one statement the way the studio treats it."""
    statement, error = clean(sql)
    if error:
        return {'ok': False, 'statement': sql, 'error': error,
                'code': 'STUDIO-001', 'elapsed_ms': 0}
    verb, kind = classify(statement)
    base = {'statement': statement, 'verb': verb, 'kind': kind}

    if kind == 'blocked':
        return {**base, 'ok': False, 'elapsed_ms': 0, 'code': 'STUDIO-002',
                'error': (f'{verb} is not available in this session. The studio is a '
                          'read-only simulation: schema changes, transaction control and '
                          'engine settings would let a typo damage the portal.')}
    if kind == 'unknown':
        return {**base, 'ok': False, 'elapsed_ms': 0, 'code': 'STUDIO-003',
                'error': (f'{verb or "That statement"} is not something this session runs. '
                          'Use SELECT, WITH, VALUES, TABLE or EXPLAIN.')}
    if verb in WRITE_VERBS and (
            'login_history' in statement.lower() or 'staff_activity' in statement.lower()):
        return {**base, 'ok': False, 'elapsed_ms': 0, 'code': 'STUDIO-004',
                'error': ('The sign-in history and the change log are append-only. They '
                          'cannot be written from any client, including this one.')}

    started = time.perf_counter()
    if kind == 'write':
        # EXPLAIN compiles the statement without running it: a real prepare step.
        try:
            db_pool.execute_query('EXPLAIN ' + statement, fetch='table')
            elapsed = round((time.perf_counter() - started) * 1000, 1)
            return {**base, 'ok': True, 'kind': 'prepare', 'elapsed_ms': elapsed,
                    'row_count': None, 'columns': [], 'rows': [], 'shown': 0,
                    'truncated': 0,
                    'message': 'Statement prepared successfully.',
                    'note': _READ_ONLY_NOTE}
        except Exception as exc:
            elapsed = round((time.perf_counter() - started) * 1000, 1)
            return {**base, 'ok': False, 'elapsed_ms': elapsed, 'code': 'STUDIO-005',
                    'error': str(exc).strip() or 'The engine rejected that statement.'}

    try:
        table = db_pool.execute_query(statement, fetch='table')
        elapsed = round((time.perf_counter() - started) * 1000, 1)
        payload = _grid(table['rows'] or [], list(table['columns']), elapsed)
        return {**base, 'ok': True, **payload,
                'message': f'{payload["row_count"]:,} row'
                           f'{"" if payload["row_count"] == 1 else "s"} fetched.',
                'note': ''}
    except Exception as exc:  # the engine's own message is the most useful feedback
        elapsed = round((time.perf_counter() - started) * 1000, 1)
        return {**base, 'ok': False, 'elapsed_ms': elapsed, 'code': 'STUDIO-006',
                'error': str(exc).strip() or 'The engine rejected that statement.'}


def run_script(text):
    """Run a whole worksheet, one statement at a time, and report every step."""
    statements = split_script(text)
    if not statements:
        return {'ok': False, 'statements': [], 'error': (
            'There is nothing to run: the worksheet is empty, or holds only comments.')}
    results = []
    for position, item in enumerate(statements, start=1):
        outcome = run(item['sql'])
        outcome['index'] = position
        outcome['offset'] = item['offset']
        results.append(outcome)
    failed = [item for item in results if not item['ok']]
    prepared = [item for item in results if item.get('kind') == 'prepare']
    return {
        'ok': not failed,
        'statements': results,
        'total': len(results),
        'succeeded': len(results) - len(failed),
        'failed': len(failed),
        'prepared': len(prepared),
        'elapsed_ms': round(sum(item['elapsed_ms'] for item in results), 1),
        'note': _READ_ONLY_NOTE if prepared else '',
    }


# ---------------------------------------------------------------------------
# the plan
# ---------------------------------------------------------------------------
def _plan_rows(sql):
    verb, kind = classify(sql)
    if kind == 'read' and verb != 'EXPLAIN':
        engine_sql = 'EXPLAIN QUERY PLAN ' + sql
    else:
        engine_sql = sql if verb == 'EXPLAIN' else 'EXPLAIN QUERY PLAN ' + sql
    return db_pool.execute_query(engine_sql, fetch='table')


def explain(sql):
    """The plan as the client draws it: nested steps, with a verdict."""
    statement, error = clean(sql)
    if error:
        return {'ok': False, 'error': error, 'code': 'STUDIO-001', 'nodes': []}
    verb, kind = classify(statement)
    if kind == 'blocked':
        return {'ok': False, 'code': 'STUDIO-002', 'nodes': [],
                'error': f'{verb} cannot be planned in this session.'}
    started = time.perf_counter()
    try:
        table = _plan_rows(statement)
    except Exception as exc:
        return {'ok': False, 'nodes': [], 'code': 'STUDIO-007',
                'error': str(exc).strip() or 'The engine could not plan that statement.',
                'elapsed_ms': round((time.perf_counter() - started) * 1000, 1)}
    elapsed = round((time.perf_counter() - started) * 1000, 1)
    rows = table['rows'] or []
    by_parent = {}
    for row in rows:
        by_parent.setdefault(row.get('parent'), []).append(row)
    nodes = []

    def visit(parent, depth):
        for row in by_parent.get(parent, []):
            detail = str(row.get('detail') or '')
            lowered = detail.lower()
            if 'scan' in lowered and 'search' not in lowered:
                kind_name = 'scan'
            elif 'search' in lowered or 'index' in lowered:
                kind_name = 'index'
            else:
                kind_name = 'other'
            nodes.append({'id': row.get('id'), 'parent': parent, 'depth': depth,
                          'detail': detail, 'kind': kind_name})
            visit(row.get('id'), depth + 1)

    visit(0, 0)
    for row in rows:                                   # anything orphaned by the engine
        if row.get('id') not in {node['id'] for node in nodes}:
            nodes.append({'id': row.get('id'), 'parent': 0, 'depth': 0,
                          'detail': str(row.get('detail') or ''), 'kind': 'other'})
    scans = [node for node in nodes if node['kind'] == 'scan']
    return {
        'ok': True, 'statement': statement, 'nodes': nodes, 'elapsed_ms': elapsed,
        'verdict': 'scan' if scans else 'index',
        'summary': (f'{len(scans)} full table scan{"" if len(scans) == 1 else "s"} in '
                    f'{len(nodes)} step{"" if len(nodes) == 1 else "s"}. '
                    + ('Fine at this size; an index on the filtered column would avoid it.'
                       if scans else 'Every access goes through an index.')),
    }


def describe(name):
    """Object details for the navigator's right-hand click menu."""
    for table in workshop.tables():
        if table.lower() == (name or '').lower():
            return {'ok': True, 'type': 'table', 'name': table,
                    'rows': _table_row_count(table),
                    'columns': workshop.columns(table),
                    'foreign_keys': workshop.foreign_keys(table),
                    'indexes': [index for index in workshop.indexes()
                                if index['table'] == table]}
    for view in workshop.views():
        if view['name'].lower() == (name or '').lower():
            return {'ok': True, 'type': 'view', 'name': view['name'],
                    'columns': workshop.columns(view['name']),
                    'purpose': view.get('purpose', ''), 'ddl': view.get('ddl', '')}
    return {'ok': False, 'error': f'No table or view called {name}.'}
