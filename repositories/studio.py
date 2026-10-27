"""SQL Studio: a desktop client over the portal's own database.

The portal's workshop explains the schema; this module gives the administrator a
client to *use* it with — the navigator, the worksheet, the result grid, the
script output and the execution plan, all driven by the running database.

The studio is **linked to the portal**: a row it inserts is the row the Students
screen shows, and a table it creates appears in Raw data on the next page load.
Every statement that writes is snapshotted first, so the change can be undone,
and the portal's own tables cannot be dropped, altered or truncated from here —
only tables the studio created can be. Oracle SQL is accepted throughout.
"""
import json
import os
import re
import time
from decimal import Decimal

from config import Config
from repositories.journal import Journal

from repositories import rawdata
from repositories import workshop
from repositories import dialect
from repositories.oracle import pseudocolumn_label
from repositories.db_pool import db_pool

MAX_ROWS = 300
_QUOTE = '`' if workshop.is_mysql() else '"'
MAX_CELL = 120
CONNECTION_NAME = 'NIST_UNIVERSITY'

READ_VERBS = {'SELECT', 'WITH', 'VALUES', 'TABLE', 'SHOW', 'DESCRIBE', 'DESC', 'EXPLAIN'}
WRITE_VERBS = {'INSERT', 'REPLACE', 'UPDATE', 'DELETE', 'MERGE'}
# Structure changes are handled above (CREATE and the DROP/ALTER family), so this
# set is only the statements that stay refused: transaction control, engine
# settings, privileges and the escape hatches around the file.
BLOCKED_VERBS = {'ATTACH', 'DETACH', 'PRAGMA', 'VACUUM', 'REINDEX', 'ANALYZE',
                 'GRANT', 'REVOKE', 'BEGIN', 'COMMIT', 'ROLLBACK', 'SAVEPOINT',
                 'RELEASE', 'SET', 'USE', 'CALL', 'EXEC', 'EXECUTE', 'LOAD', 'DO',
                 'LOCK', 'UNLOCK'}
PLACEHOLDER = '•••'


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
        'read_only': False,
        'autocommit': 'ON · each statement commits',
        'mode': 'Linked to the portal · writable, undoable',
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


CREATE_VERBS = {'CREATE'}
STRUCTURE_VERBS = {'DROP', 'ALTER', 'TRUNCATE', 'RENAME'}


def classify(sql):
    """read / write / create / drop / blocked / unknown, on comment-stripped text."""
    words = _strip_noise(sql).strip().lstrip('( ').split()
    verb = words[0].upper() if words else ''
    if verb in READ_VERBS:
        return verb, 'read'
    if verb in WRITE_VERBS:
        return verb, 'write'
    if verb == 'CREATE':
        return verb, 'create'
    if verb in STRUCTURE_VERBS:
        return verb, 'drop'
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
    labels = [pseudocolumn_label(column) for column in columns]
    return {
        'columns': [{'name': label, 'numeric': numeric[position]}
                    for position, label in enumerate(labels)],
        'rows': [{'number': number, 'cells': row}
                 for number, row in enumerate(shown, start=1)],
        'row_count': len(masked),
        'shown': len(shown),
        'truncated': len(masked) - len(shown),
        'elapsed_ms': elapsed,
    }


# ---------------------------------------------------------------------------
# the link to the portal: what the studio may change, and how it is undone
# ---------------------------------------------------------------------------
APPEND_ONLY = ('login_history', 'staff_activity')


def _state_dir():
    directory = os.path.join(os.path.dirname(str(Config.SQLITE_PATH)), 'studio_portal_journal')
    os.makedirs(directory, exist_ok=True)
    return directory


def _ownership_file():
    return os.path.join(_state_dir(), 'created.json')


def _read_owned():
    """Every name this client has ever created, lower-cased, kept on disk."""
    try:
        with open(_ownership_file(), 'r', encoding='utf-8') as handle:
            data = json.load(handle)
        names = data.get('created', []) if isinstance(data, dict) else data
        return sorted({str(name).strip().lower() for name in names if str(name).strip()})
    except (OSError, ValueError, AttributeError):
        return []


def _remember_owned(*names):
    owned = _read_owned()
    for name in names:
        clean_name = str(name or '').strip().lower()
        if clean_name and clean_name not in owned:
            owned.append(clean_name)
    try:
        with open(_ownership_file(), 'w', encoding='utf-8') as handle:
            json.dump({'created': sorted(owned)}, handle, indent=2)
    except OSError:
        pass


def portal_tables():
    """The portal's own tables: everything this client did not create.

    Ownership is recorded when the studio creates an object, so a table that
    existed before the studio was ever opened can never be dropped, altered or
    truncated from here — including tables added by a later migration.
    """
    try:
        existing = {str(name).lower() for name in rawdata.table_names()}
    except Exception:
        return set()
    return existing - set(_read_owned())


def studio_created():
    """Objects this client added that still exist, for the navigator badge."""
    try:
        existing = {str(name).lower() for name in rawdata.table_names()}
    except Exception:
        return set()
    return existing & set(_read_owned())


def _object_of(statement):
    """The table name a DROP/ALTER/TRUNCATE statement is aimed at."""
    match = re.search(
        r'\b(?:table|view|index)\s+("?[A-Za-z_][A-Za-z0-9_$#]*"?)|'
        r'\btruncate\s+(?:table\s+)?"?([A-Za-z_][A-Za-z0-9_$#]*)"?',
        _strip_noise(statement), re.I)
    if not match:
        return ''
    return (match.group(1) or match.group(2) or '').strip().strip('"').lower()


def portal_journal():
    """The undo stack for the portal file itself."""
    return Journal(Config.SQLITE_PATH, _state_dir(), limit=12, noun='portal change')


def journal_state():
    return portal_journal().state()


def undo():
    payload = portal_journal().undo()
    if payload.get('ok'):
        payload['catalogue'] = catalogue()
    return payload


def redo():
    payload = portal_journal().redo()
    if payload.get('ok'):
        payload['catalogue'] = catalogue()
    return payload


_OBJECT_NOUNS = {'TABLE': 'Table', 'VIEW': 'View', 'INDEX': 'Index',
                 'SEQUENCE': 'Sequence', 'DATABASE': 'Database'}


def _ddl_message(verb, statement, done):
    """`Table created.` / `View dropped.` — the noun Oracle would print."""
    words = _strip_noise(statement).split()
    noun = ''
    for index, word in enumerate(words[1:5], start=1):
        candidate = word.upper().lstrip('(')
        if candidate in _OBJECT_NOUNS:
            noun = _OBJECT_NOUNS[candidate]
            break
        if candidate in ('OR', 'REPLACE', 'UNIQUE', 'GLOBAL', 'TEMPORARY', 'IF', 'NOT', 'EXISTS'):
            continue
    if verb == 'TRUNCATE':
        noun = 'Table'
    return f'{noun or "Object"} {done}.'


def _keep_name_case(engine_sql, name):
    """Oracle folds an unquoted name to upper case; the portal's own screens and
    the raw-data browser match names case-sensitively, so a table created here
    keeps the spelling the administrator typed."""
    if not engine_sql or not name:
        return engine_sql
    folded = '"%s"' % name.upper()
    if folded not in engine_sql:
        return engine_sql
    return engine_sql.replace(folded, '"%s"' % name)


def _write(statement, verb, kind):
    """Run a real change against the portal, with a snapshot taken first."""
    protected = portal_tables()
    if kind == 'drop':
        target = _object_of(statement)
        if target in APPEND_ONLY:
            return {'ok': False, 'code': 'STUDIO-004', 'error': (
                'The sign-in history and the change log are append-only. They cannot be '
                'dropped, altered or truncated, not even from this client.')}
        if target in protected:
            return {'ok': False, 'code': 'STUDIO-007', 'error': (
                f'{target} belongs to the portal. The studio will not drop, alter or '
                'truncate a portal table: use the management screens, or the practice '
                'schema connection (ORACLE_XE) if you want to try it on a copy.')}
    if verb in WRITE_VERBS and re.search(r'\b(login_history|staff_activity)\b',
                                         statement.lower()):
        return {'ok': False, 'code': 'STUDIO-004', 'error': (
            'The sign-in history and the change log are append-only. They cannot be '
            'written from any client, including this one.')}

    journal = portal_journal()
    if not journal.record(statement, verb):
        return {'ok': False, 'code': 'STUDIO-008', 'error': (
            'The studio could not take a snapshot of the database, so it will not change '
            'it: without a snapshot there would be no way to undo this statement.')}

    started = time.perf_counter()
    try:
        engine_sql, notes = dialect.to_engine(statement)
        engine_sql = _keep_name_case(engine_sql, _object_of(statement))
        result = db_pool.execute_dml(engine_sql)
    except Exception as exc:
        journal.forget()
        elapsed = round((time.perf_counter() - started) * 1000, 1)
        return {'ok': False, 'code': 'STUDIO-009', 'elapsed_ms': elapsed,
                'error': str(exc).strip() or 'The engine rejected that statement.'}

    elapsed = round((time.perf_counter() - started) * 1000, 1)
    if kind == 'create' and verb == 'CREATE':
        _remember_owned(_object_of(statement))
    affected = result.get('rowcount')
    affected = 0 if affected is None or affected < 0 else affected
    if kind == 'create':
        message = _ddl_message(verb, statement, 'created')
    elif verb == 'INSERT':
        message = f'{affected:,} row{"" if affected == 1 else "s"} created.'
    elif verb in ('UPDATE',):
        message = f'{affected:,} row{"" if affected == 1 else "s"} updated.'
    elif verb == 'DELETE':
        message = f'{affected:,} row{"" if affected == 1 else "s"} deleted.'
    elif kind == 'drop':
        message = _ddl_message(verb, statement, 'dropped' if verb in ('DROP', 'TRUNCATE')
                               else 'altered')
    else:
        message = f'{affected:,} row{"" if affected == 1 else "s"} changed.'
    return {'ok': True, 'kind': 'ddl' if kind != 'write' else 'write', 'verb': verb,
            'statement': statement, 'message': message, 'affected': affected,
            'elapsed_ms': elapsed, 'translated': engine_sql,
            'notes': notes, 'row_count': None, 'columns': [], 'rows': [],
            'shown': 0, 'truncated': 0, 'journal': journal.state()}


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
                'error': (f'{verb} is refused in this window. Transaction control, engine '
                          'settings and privilege statements are blocked so a typo cannot '
                          'strand the database; data and schema changes do run for real.')}
    if kind == 'unknown':
        return {**base, 'ok': False, 'elapsed_ms': 0, 'code': 'STUDIO-003',
                'error': (f'{verb or "That statement"} is not something this session runs. '
                          'Use SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, ALTER or '
                          'TRUNCATE.')}

    if verb == 'EXPLAIN':
        return explain(statement)

    if kind in ('write', 'create', 'drop'):
        payload = _write(statement, verb, kind)
        if not payload['ok']:
            return {**base, **payload, 'elapsed_ms': payload.get('elapsed_ms', 0)}
        return {**base, **payload}

    started = time.perf_counter()
    try:
        engine_sql, notes = dialect.to_engine(statement)
        table = db_pool.execute_query(statement, fetch='table')
        elapsed = round((time.perf_counter() - started) * 1000, 1)
        payload = _grid(table['rows'] or [], list(table['columns']), elapsed)
        return {**base, 'ok': True, **payload,
                'message': f'{payload["row_count"]:,} row'
                           f'{"" if payload["row_count"] == 1 else "s"} fetched.',
                'translated': engine_sql if engine_sql != statement else None,
                'notes': notes, 'note': ''}
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
        'note': '',
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
