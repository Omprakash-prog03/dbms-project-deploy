"""Oracle Express simulation: a writable practice schema that speaks Oracle SQL.

The portal's own data lives in SQLite and stays read-only in the studio. This
module adds a *second connection* to the studio — ``ORACLE_XE`` — which accepts
Oracle SQL the way a real SQL*Plus session would:

    CREATE TABLE emp (empno NUMBER(4) PRIMARY KEY, ename VARCHAR2(20));
    INSERT INTO emp VALUES (1, 'SMITH');
    SELECT ename FROM emp WHERE ROWNUM <= 5;
    SELECT USER, SYSDATE FROM dual;

Each statement is translated to SQLite and executed against a separate scratch
database, so ``CREATE``, ``INSERT``, ``UPDATE``, ``DELETE``, ``DROP`` and
``TRUNCATE`` genuinely do what they say — without touching a single portal row.

Everything the client shows is Oracle-shaped: upper-case column names, Oracle
type names in ``DESCRIBE``, ``ORA-00942``-style errors, and the classic messages
(``Table created.``, ``1 row created.``). The translated statement is returned
with every result so the translation is never hidden from the reader.
"""
import json
import os
import re
import shutil
import sqlite3
import time
import uuid
from datetime import datetime, timezone

from config import Config, BASE_DIR
from repositories.journal import Journal

CONNECTION_NAME = 'ORACLE_XE'
JOURNAL_LIMIT = 12
JOURNAL_DIR = 'instance/studio_oracle_journal'
PRODUCT = 'Oracle Database 21c Express Edition'
USER = 'STUDIO'
MAX_ROWS = 300
MAX_CELL = 120
PLACEHOLDER = '•••'

_META_PREFIX = '_'

# Words Oracle treats as reserved; used to keep column names honest.
_NON_TYPE_WORDS = {
    'DEFAULT', 'NOT', 'NULL', 'PRIMARY', 'KEY', 'UNIQUE', 'REFERENCES', 'CHECK',
    'CONSTRAINT', 'GENERATED', 'ALWAYS', 'BY', 'IDENTITY', 'ON', 'ENABLE', 'DISABLE',
    'COLLATE', 'COMMENT', 'VISIBLE', 'INVISIBLE', 'VIRTUAL',
}

_UNSUPPORTED = {
    'MERGE': ('ORA-00933', 'MERGE is not available in this simulation.',
              'The statement is valid Oracle; the simulator translates a smaller dialect. '
              'MERGE, hierarchical CONNECT BY and analytic windows over named windows are '
              'documented in the workshop instead.'),
    'CONNECT': ('ORA-00933', 'Hierarchical queries (CONNECT BY) are not available here.',
                'Oracle walks a tree with CONNECT BY / PRIOR. The same walk is written as a '
                'recursive CTE in db/queries/windows_ctes.sql and shown on the workshop page.'),
    'PIVOT': ('ORA-00933', 'PIVOT is not available in this simulation.',
              'Use conditional aggregation (SUM(CASE WHEN …)) as the workshop demonstrates.'),
}


# ---------------------------------------------------------------------------
# the practice database
# ---------------------------------------------------------------------------
def path():
    """The scratch file. Never the portal database."""
    configured = os.getenv('STUDIO_ORACLE_PATH') or 'instance/studio_oracle.db'
    candidate = os.path.abspath(os.path.join(str(BASE_DIR), configured))
    portal = os.path.abspath(str(getattr(Config, 'SQLITE_PATH', '') or ''))
    if candidate == portal:                       # a misconfiguration must not point at the portal
        candidate = os.path.abspath(os.path.join(str(BASE_DIR), 'instance/studio_oracle.db'))
    os.makedirs(os.path.dirname(candidate), exist_ok=True)
    return candidate


def _connect():
    connection = sqlite3.connect(path(), timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys = ON')
    return connection


def _meta(connection):
    """Internal bookkeeping: declared Oracle types, sequences and comments."""
    connection.execute(
        'CREATE TABLE IF NOT EXISTS _column ('
        ' table_name TEXT NOT NULL, column_name TEXT NOT NULL, oracle_type TEXT,'
        ' sqlite_type TEXT, nullable INTEGER, position INTEGER, default_value TEXT,'
        ' PRIMARY KEY (table_name, column_name))')
    connection.execute(
        'CREATE TABLE IF NOT EXISTS _sequence ('
        ' name TEXT PRIMARY KEY, current_value INTEGER, increment_by INTEGER)')
    connection.execute(
        'CREATE TABLE IF NOT EXISTS _comment ('
        ' object_type TEXT NOT NULL, object_name TEXT NOT NULL, column_name TEXT,'
        ' text TEXT, PRIMARY KEY (object_type, object_name, column_name))')


SEED = """
CREATE TABLE dept (
  deptno NUMBER(2) PRIMARY KEY,
  dname  VARCHAR2(14),
  loc    VARCHAR2(13)
);

CREATE TABLE emp (
  empno    NUMBER(4) PRIMARY KEY,
  ename    VARCHAR2(10),
  job      VARCHAR2(9),
  mgr      NUMBER(4),
  hiredate DATE,
  sal      NUMBER(7,2),
  comm     NUMBER(7,2),
  deptno   NUMBER(2) REFERENCES dept (deptno)
);

CREATE INDEX emp_deptno_idx ON emp (deptno);
CREATE SEQUENCE emp_seq START WITH 8000 INCREMENT BY 1;

COMMENT ON TABLE emp IS 'The classic Oracle demonstration table: one row per employee.';
COMMENT ON TABLE dept IS 'Departments. Each employee belongs to exactly one.';
COMMENT ON COLUMN emp.sal IS 'Monthly salary, in rupees.';
COMMENT ON COLUMN emp.comm IS 'Commission, NULL for most staff.';

INSERT INTO dept VALUES (10, 'ACCOUNTING', 'NEW YORK');
INSERT INTO dept VALUES (20, 'RESEARCH', 'DALLAS');
INSERT INTO dept VALUES (30, 'SALES', 'CHICAGO');
INSERT INTO dept VALUES (40, 'OPERATIONS', 'BOSTON');

INSERT INTO emp VALUES (7369, 'SMITH', 'CLERK', 7902, DATE '1980-12-17', 800, NULL, 20);
INSERT INTO emp VALUES (7499, 'ALLEN', 'SALESMAN', 7698, DATE '1981-02-20', 1600, 300, 30);
INSERT INTO emp VALUES (7521, 'WARD', 'SALESMAN', 7698, DATE '1981-02-22', 1250, 500, 30);
INSERT INTO emp VALUES (7566, 'JONES', 'MANAGER', 7839, DATE '1981-04-02', 2975, NULL, 20);
INSERT INTO emp VALUES (7654, 'MARTIN', 'SALESMAN', 7698, DATE '1981-09-28', 1250, 1400, 30);
INSERT INTO emp VALUES (7698, 'BLAKE', 'MANAGER', 7839, DATE '1981-05-01', 2850, NULL, 30);
INSERT INTO emp VALUES (7782, 'CLARK', 'MANAGER', 7839, DATE '1981-06-09', 2450, NULL, 10);
INSERT INTO emp VALUES (7788, 'SCOTT', 'ANALYST', 7566, DATE '1987-04-19', 3000, NULL, 20);
INSERT INTO emp VALUES (7839, 'KING', 'PRESIDENT', NULL, DATE '1981-11-17', 5000, NULL, 10);
INSERT INTO emp VALUES (7844, 'TURNER', 'SALESMAN', 7698, DATE '1981-09-08', 1500, 0, 30);
INSERT INTO emp VALUES (7876, 'ADAMS', 'CLERK', 7788, DATE '1987-05-23', 1100, NULL, 20);
INSERT INTO emp VALUES (7900, 'JAMES', 'CLERK', 7698, DATE '1981-12-03', 950, NULL, 30);
INSERT INTO emp VALUES (7902, 'FORD', 'ANALYST', 7566, DATE '1981-12-03', 3000, NULL, 20);
INSERT INTO emp VALUES (7934, 'MILLER', 'CLERK', 7782, DATE '1982-01-23', 1300, NULL, 10);
"""


def ensure_schema(seeding=False):
    """Create the practice schema once, the way a fresh XE install arrives."""
    with _connect() as connection:
        _meta(connection)
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'EMP'").fetchone()
    if exists or seeding:
        return False
    for item in split_script(SEED):
        run(item['sql'], seeding=True)
    return True


def reset():
    """Drop every object in the practice schema and seed it again."""
    with _connect() as connection:
        _meta(connection)
        objects = [dict(row) for row in connection.execute(
            "SELECT type, name FROM sqlite_master WHERE type IN ('table','view','index','trigger') "
            "AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '\\_%' ESCAPE '\\'")]
        connection.execute('PRAGMA foreign_keys = OFF')
        for item in reversed(objects):
            try:
                connection.execute(f'DROP {item["type"].upper()} IF EXISTS "{item["name"]}"')
            except sqlite3.Error:
                continue
        connection.execute('DELETE FROM _column')
        connection.execute('DELETE FROM _sequence')
        connection.execute('DELETE FROM _comment')
        connection.commit()
    clear_journal()
    ensure_schema()
    return {'ok': True, 'message': 'Practice schema reset.', 'tables': len(catalogue()['tables'])}


# ---------------------------------------------------------------------------
# the change journal: every writable statement can be undone
# ---------------------------------------------------------------------------
_WRITABLE = {'CREATE', 'DROP', 'ALTER', 'TRUNCATE', 'COMMENT', 'RENAME',
             'INSERT', 'UPDATE', 'DELETE'}


def journal_path():
    """The snapshots live beside the practice file, never beside the portal's."""
    directory = os.path.join(os.path.dirname(path()), os.path.basename(JOURNAL_DIR))
    os.makedirs(directory, exist_ok=True)
    return directory


def _journal():
    """The practice schema's own undo stack, bound to the file it protects."""
    return Journal(path(), journal_path(), limit=JOURNAL_LIMIT, noun='change')


def journal_state():
    return _journal().state()


def _journal_record(sql, verb):
    if verb not in _WRITABLE:
        return False
    ensure_schema()
    return _journal().record(sql, verb)


def _journal_forget():
    _journal().forget()


def undo():
    """Put the practice schema back exactly as it was before the last change."""
    payload = _journal().undo()
    if payload.get('ok'):
        payload['catalogue'] = catalogue()
    return payload


def redo():
    """Replay the change that undo took back."""
    payload = _journal().redo()
    if payload.get('ok'):
        payload['catalogue'] = catalogue()
    return payload


def clear_journal():
    _journal().clear()


# ---------------------------------------------------------------------------
# statement splitting (Oracle clients end a statement with ; or a lone /)
# ---------------------------------------------------------------------------
def split_script(text):
    """Split a script on semicolons, respecting quotes, comments and PL/SQL blocks."""
    statements = []
    buffer = []
    index = 0
    length = len(text or '')
    quote = ''
    line_comment = False
    block_comment = False
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
        if char in ("'", '"'):
            quote = char
            buffer.append(char)
            index += 1
            continue
        if char == ';':
            statement = ''.join(buffer).strip()
            if _bare(statement):
                statements.append({'sql': statement, 'offset': start})
            buffer = []
            index += 1
            start = index
            continue
        buffer.append(char)
        index += 1
    tail = ''.join(buffer).strip()
    if _bare(tail):
        statements.append({'sql': tail, 'offset': start})
    return statements


def _bare(text):
    stripped = re.sub(r'/\*.*?\*/', ' ', text or '', flags=re.S)
    stripped = re.sub(r'--[^\n]*', ' ', stripped)
    return bool(stripped.strip())


def _strip_leading_comments(text):
    """A note above a statement is not part of it, the way a client treats it."""
    stripped = text.lstrip()
    while True:
        if stripped.startswith('--'):
            cut = stripped.find('\n')
            if cut == -1:
                return ''
            stripped = stripped[cut + 1:].lstrip()
            continue
        if stripped.startswith('/*'):
            cut = stripped.find('*/')
            if cut == -1:
                return stripped
            stripped = stripped[cut + 2:].lstrip()
            continue
        return stripped


def clean(sql):
    """One statement, no trailing semicolon or SQL*Plus slash."""
    text = (sql or '').strip()
    if text == '/':
        return '', 'Nothing to run.'
    if text.endswith('/') and not text.endswith('*/') and '\n' in text:
        text = text.rsplit('\n', 1)[0].rstrip() if text.rsplit('\n', 1)[1].strip() == '/' else text
    text = _strip_leading_comments(text)
    body = text.rstrip().rstrip(';').strip()
    if not _bare(body):
        return '', 'Nothing to run: the editor is empty, or holds only comments.'
    core = re.sub(r'/\*.*?\*/', ' ', body, flags=re.S)
    core = re.sub(r'--[^\n]*', ' ', core)
    if ';' in core.strip().rstrip(';'):
        return '', ('That is more than one statement. Press F5 to run the script, or place '
                    'the cursor on one statement and press F9.')
    return text.rstrip().rstrip(';').strip(), ''


# ---------------------------------------------------------------------------
# translation: Oracle -> SQLite
# ---------------------------------------------------------------------------
def _sqlite_type(declared):
    """The SQLite storage class behind an Oracle type."""
    base = re.sub(r'\(.*\)', '', declared or '').strip().upper()
    base = re.sub(r'\s+', ' ', base)
    if base.startswith('TIMESTAMP') or base.startswith('INTERVAL'):
        return 'TEXT'
    if base in {'VARCHAR2', 'VARCHAR', 'NVARCHAR2', 'NVARCHAR', 'CHAR', 'NCHAR', 'CLOB',
                'NCLOB', 'LONG', 'XMLTYPE', 'ROWID', 'UROWID'}:
        return 'TEXT'
    if base in {'NUMBER', 'DECIMAL', 'DEC', 'NUMERIC', 'INTEGER', 'INT', 'SMALLINT',
                'BINARY_INTEGER', 'PLS_INTEGER'}:
        match = re.match(r'\(\s*(\d+)\s*(?:,\s*(-?\d+)\s*)?\)', declared or '')
        if match and (match.group(2) in (None, '0')):
            return 'INTEGER'
        return 'NUMERIC'
    if base in {'FLOAT', 'BINARY_FLOAT', 'BINARY_DOUBLE', 'REAL', 'DOUBLE PRECISION'}:
        return 'REAL'
    if base in {'DATE'}:
        return 'TEXT'
    if base in {'BLOB', 'RAW', 'LONG RAW', 'BFILE'}:
        return 'BLOB'
    if base == 'BOOLEAN':
        return 'INTEGER'
    return 'TEXT'


def _identifier(text):
    """Oracle folds an unquoted identifier to upper case and keeps a quoted one as typed."""
    text = (text or '').strip()
    if text.startswith('"') and text.endswith('"'):
        return text[1:-1], True
    return text.upper(), False


def _match_paren(text, start):
    if start >= len(text) or text[start] != '(':
        return None
    depth = 0
    index = start
    while index < len(text):
        char = text[index]
        if char in ("'", '"'):
            quote = char
            index += 1
            while index < len(text):
                if text[index] == quote:
                    if index + 1 < len(text) and text[index + 1] == quote:
                        index += 2
                        continue
                    break
                index += 1
        elif char == '(':
            depth += 1
        elif char == ')':
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return None


def _split_args(text):
    """Split a function's arguments, respecting parentheses and quoted strings."""
    parts, depth, current, quote = [], 0, [], ''
    for character in text:
        if quote:
            current.append(character)
            if character == quote:
                quote = ''
            continue
        if character in ("'", '"'):
            quote = character
            current.append(character)
            continue
        if character == '(':
            depth += 1
        elif character == ')':
            depth -= 1
        if character == ',' and depth == 0:
            parts.append(''.join(current).strip())
            current = []
        else:
            current.append(character)
    parts.append(''.join(current).strip())
    return parts


def _strftime_pattern(oracle_format):
    pattern = oracle_format
    for token, replacement in (
            ('YYYY', '%Y'), ('YY', '%y'), ('MM', '%m'), ('MON', '%m'), ('MONTH', '%m'),
            ('DD', '%d'), ('HH24', '%H'), ('HH12', '%I'), ('HH', '%H'), ('MI', '%M'),
            ('SS', '%S')):
        pattern = pattern.replace(token, replacement)
    return pattern


def _rewrite_calls(sql):
    """Rewrite Oracle functions inside a statement, leaving string literals alone."""
    out = []
    index = 0
    length = len(sql)
    while index < length:
        char = sql[index]
        if char in ("'", '"'):
            quote = char
            cursor = index + 1
            while cursor < length:
                if sql[cursor] == quote:
                    if cursor + 1 < length and sql[cursor + 1] == quote:
                        cursor += 2
                        continue
                    cursor += 1
                    break
                cursor += 1
            out.append(sql[index:cursor])
            index = cursor
            continue
        word = re.match(r'[A-Za-z_][A-Za-z0-9_$#]*', sql[index:])
        if word:
            name = word.group(0)
            cursor = index + len(name)
            if cursor < length and sql[cursor] == '(':
                close = _match_paren(sql, cursor)
                if close is not None:
                    args = sql[cursor + 1:close]
                    replacement = _call(name.upper(), args)
                    if replacement is not None:
                        out.append(replacement)
                    else:
                        out.append(f'{name}({_rewrite_calls(args)})')
                    index = close + 1
                    continue
            out.append(name)
            index = cursor
            continue
        out.append(char)
        index += 1
    return ''.join(out)


def _call(name, args):
    parts = _split_args(args)
    upper = [part.upper() for part in parts]
    if name == 'NVL' and len(parts) == 2:
        return f'IFNULL({parts[0]}, {parts[1]})'
    if name == 'NVL2' and len(parts) == 3:
        return f'(CASE WHEN {parts[0]} IS NOT NULL THEN {parts[1]} ELSE {parts[2]} END)'
    if name == 'DECODE' and len(parts) >= 3:
        expression = parts[0]
        pairs = parts[1:]
        default = 'NULL'
        if len(pairs) % 2:
            default = pairs[-1]
            pairs = pairs[:-1]
        branches = ' '.join(f'WHEN {pairs[i]} THEN {pairs[i + 1]}'
                            for i in range(0, len(pairs), 2))
        return f'(CASE {expression} {branches} ELSE {default} END)'
    if name == 'TO_CHAR':
        if len(parts) == 1:
            return f'CAST({parts[0]} AS TEXT)'
        pattern = parts[1].strip().strip("'")
        return f"strftime('{_strftime_pattern(pattern)}', {parts[0]})"
    if name == 'TO_DATE':
        if len(parts) >= 2 and parts[0].startswith("'"):
            return f"date({parts[0]})"
        return f'date({parts[0]})'
    if name == 'TO_NUMBER':
        return f'CAST({parts[0]} AS NUMERIC)'
    if name == 'MOD' and len(parts) == 2:
        return f'({parts[0]} % {parts[1]})'
    if name in {'TRUNC', 'TRUNCATE'} and parts:
        return f'CAST({parts[0]} AS INTEGER)'
    if name == 'LISTAGG' and parts:
        separator = parts[1] if len(parts) > 1 else "','"
        return f'GROUP_CONCAT({parts[0]}, {separator})'
    if name == 'NANVL' and len(parts) == 2:
        return f'IFNULL(NULLIF({parts[0]}, {parts[0]}), {parts[1]})'
    if name == 'INITCAP':
        return f'({parts[0]})'
    return None


def translate(sql, user=None, sequences=True):
    """Return ``(sqlite_sql, notes)`` for a single Oracle statement.

    ``user`` is what Oracle's USER pseudo-column should report, and ``sequences``
    says whether NEXTVAL/CURRVAL may reach into this practice schema. The portal
    uses the same translator with ``user`` set to the signed-in account and
    ``sequences`` off, so Oracle syntax works on every screen without a screen
    being able to advance a sequence it does not own.
    """
    notes = []
    text = sql.strip().rstrip(';').strip()
    upper = re.sub(r'--[^\n]*', ' ', text).upper()

    # Sequences are resolved before translation: Oracle's NEXTVAL is a side effect.
    if sequences:
        text = re.sub(r'\b([A-Za-z0-9_$#]+)\s*\.\s*NEXTVAL\b',
                      lambda match: str(_next_value(match.group(1))), text, flags=re.I)
        text = re.sub(r'\b([A-Za-z0-9_$#]+)\s*\.\s*CURRVAL\b',
                      lambda match: str(_current_value(match.group(1))), text, flags=re.I)

    verb = _verb(text)
    if verb == 'DESCRIBE':
        return '', ['descriptive']

    # Row limiting
    limit = None
    rownum = re.search(r'\bROWNUM\s*(<=|<|=)\s*(\d+)\b', text, re.I)
    if rownum and verb in ('SELECT', 'WITH'):
        bound = int(rownum.group(2))
        limit = bound if rownum.group(1) in ('<=', '=') else max(bound - 1, 0)
        text = re.sub(r'\bAND\s+ROWNUM\s*(<=|<|=)\s*\d+\b', '', text, flags=re.I)
        text = re.sub(r'\bROWNUM\s*(<=|<|=)\s*\d+\s+AND\s+', '', text, flags=re.I)
        text = re.sub(r'\bWHERE\s+ROWNUM\s*(<=|<|=)\s*\d+\b', '', text, flags=re.I)
        notes.append(f'ROWNUM converted to LIMIT {limit}.')
    fetch = re.search(r'\bOFFSET\s+(\d+)\s+ROWS?\s+FETCH\s+(?:NEXT|FIRST)\s+(\d+)\s+ROWS?\s+ONLY', text, re.I)
    if fetch:
        text = text[:fetch.start()].rstrip()
        text = f'{text} LIMIT {int(fetch.group(2))} OFFSET {int(fetch.group(1))}'
        notes.append('OFFSET … FETCH converted to LIMIT … OFFSET.')
    else:
        fetch_first = re.search(r'\bFETCH\s+(?:NEXT|FIRST)\s+(\d+)\s+ROWS?\s+ONLY', text, re.I)
        if fetch_first:
            limit = int(fetch_first.group(1))
            text = text[:fetch_first.start()].rstrip()
            notes.append(f'FETCH FIRST {limit} ROWS ONLY converted to LIMIT {limit}.')
    if limit is not None and ' LIMIT ' not in text.upper():
        text = f'{text} LIMIT {limit}'

    # DDL is translated structurally; DML and queries by expression.
    if verb in {'CREATE', 'DROP', 'ALTER', 'TRUNCATE', 'COMMENT', 'RENAME'}:
        return _translate_ddl(text, verb), notes

    text = re.sub(r'\bDATE\s+\'', "'", text)
    text = re.sub(r'\bTIMESTAMP\s+\'', "'", text)
    text = re.sub(r'\bSYSTIMESTAMP\b', "datetime('now')", text, flags=re.I)
    text = re.sub(r'\bSYSDATE\b', "datetime('now')", text, flags=re.I)
    text = re.sub(r'\bCURRENT_DATE\b', "date('now')", text, flags=re.I)
    text = re.sub(r'\bCURRENT_TIMESTAMP\b', "datetime('now')", text, flags=re.I)
    text = re.sub(r'\bUSER\b', f"'{user or USER}'", text)
    text = re.sub(r'\bMINUS\b', 'EXCEPT', text, flags=re.I)
    text = re.sub(r'\bFROM\s+DUAL\b', 'FROM (SELECT 1 AS DUMMY)', text, flags=re.I)
    text = re.sub(r'\bROWNUM\b', 'ROW_NUMBER() OVER ()', text, flags=re.I)
    text = _rewrite_calls(text)
    text = re.sub(r'\s+WITHIN\s+GROUP\s*\(\s*ORDER\s+BY[^)]*\)', '', text, flags=re.I)
    if 'WITHIN GROUP' in text.upper():
        notes.append('WITHIN GROUP removed; GROUP_CONCAT orders by the group key.')
    return text, notes


def _verb(sql):
    cleaned = re.sub(r'--[^\n]*', ' ', sql).strip().lstrip('( ')
    word = (cleaned.split() or [''])[0].upper()
    if word == 'DESC':
        return 'DESCRIBE'
    return word


def _translate_ddl(sql, verb):
    upper = sql.upper()
    if verb == 'TRUNCATE':
        table = re.match(r'TRUNCATE\s+TABLE\s+([A-Za-z0-9_$#"]+)', sql, re.I)
        return f'DELETE FROM "{_identifier(table.group(1))[0] if table else ""}"'
    if verb == 'COMMENT':
        return sql                                    # handled before execution
    if verb == 'RENAME':
        match = re.match(r'RENAME\s+([A-Za-z0-9_$#"]+)\s+TO\s+([A-Za-z0-9_$#"]+)', sql, re.I)
        if match:
            old, _ = _identifier(match.group(1))
            new, _ = _identifier(match.group(2))
            return f'ALTER TABLE "{old}" RENAME TO "{new}"'
        return sql
    if verb == 'CREATE':
        if re.match(r'CREATE\s+(OR\s+REPLACE\s+)?(GLOBAL\s+TEMPORARY\s+|PRIVATE\s+TEMPORARY\s+)?TABLE\b', sql, re.I):
            return _create_table(sql)
        if re.match(r'CREATE\s+(OR\s+REPLACE\s+)?(FORCE\s+)?VIEW\b', sql, re.I):
            return _create_view(sql)
        if re.match(r'CREATE\s+(UNIQUE\s+)?(BITMAP\s+)?INDEX\b', sql, re.I):
            return _create_index(sql)
        return sql
    if verb == 'DROP':
        match = re.match(r'DROP\s+(TABLE|VIEW|INDEX|SEQUENCE|TRIGGER)\s+([A-Za-z0-9_$#"]+)', sql, re.I)
        if match:
            kind = match.group(1).upper()
            name, _ = _identifier(match.group(2))
            if kind == 'SEQUENCE':
                return sql
            return f'DROP {kind} IF EXISTS "{name}"'
        return sql
    if verb == 'ALTER':
        add = re.match(r'ALTER\s+TABLE\s+([A-Za-z0-9_$#"]+)\s+ADD\s*(\(.*\)|.+)$', sql, re.I | re.S)
        if add:
            table = _identifier(add.group(1))[0]
            body = add.group(2).strip()
            if body.startswith('(') and body.endswith(')'):
                body = body[1:-1]
            definitions = []
            for part in _split_top_level(body):
                column = _column_definition(part)
                definitions.append(f'ALTER TABLE "{table}" ADD COLUMN {column["ddl"]}')
            return '\n'.join(definitions) if definitions else sql
        drop = re.match(r'ALTER\s+TABLE\s+([A-Za-z0-9_$#"]+)\s+DROP\s+COLUMN\s+([A-Za-z0-9_$#"]+)', sql, re.I)
        if drop:
            table = _identifier(drop.group(1))[0]
            column = _identifier(drop.group(2))[0]
            return f'ALTER TABLE "{table}" DROP COLUMN "{column}"'
        rename = re.match(r'ALTER\s+TABLE\s+([A-Za-z0-9_$#"]+)\s+RENAME\s+TO\s+([A-Za-z0-9_$#"]+)', sql, re.I)
        if rename:
            old = _identifier(rename.group(1))[0]
            new = _identifier(rename.group(2))[0]
            return f'ALTER TABLE "{old}" RENAME TO "{new}"'
    if 'CASCADE CONSTRAINTS' in upper or upper.endswith('PURGE'):
        return re.sub(r'\s+(CASCADE\s+CONSTRAINTS|PURGE)\s*$', '', sql, flags=re.I)
    return sql


def _split_top_level(text):
    parts, depth, current = [], 0, []
    for character in text:
        if character == '(':
            depth += 1
        elif character == ')':
            depth -= 1
        if character == ',' and depth == 0:
            parts.append(''.join(current))
            current = []
        else:
            current.append(character)
    parts.append(''.join(current))
    return [part.strip() for part in parts if part.strip()]


def _column_definition(part):
    """Translate one column definition, keeping its Oracle type for DESCRIBE."""
    text = re.sub(r'\s+', ' ', part).strip()
    constraint_words = r'(DEFAULT|NOT\s+NULL|NULL|PRIMARY\s+KEY|UNIQUE|REFERENCES|CHECK|CONSTRAINT|GENERATED|ENABLE|DISABLE)'
    identity = bool(re.search(r'GENERATED\s+(ALWAYS|BY\s+DEFAULT)(\s+ON\s+NULL)?\s+AS\s+IDENTITY', text, re.I))
    text = re.sub(r'\s*GENERATED\s+(ALWAYS|BY\s+DEFAULT)(\s+ON\s+NULL)?\s+AS\s+IDENTITY(\s*\([^)]*\))?', '', text, flags=re.I)

    name_match = re.match(r'("[^"]+"|[A-Za-z0-9_$#]+)\s+(.*)$', text, re.S)
    if not name_match:
        return {'name': text, 'oracle_type': 'VARCHAR2(4000)', 'sqlite_type': 'TEXT',
                'nullable': True, 'default': None, 'identity': False, 'inline_pk': False,
                'unique': False, 'references': '', 'check': '', 'ddl': f'"{text}" TEXT'}
    name, quoted = _identifier(name_match.group(1))
    rest = name_match.group(2).strip()

    cut = re.search(constraint_words, rest, re.I)
    type_text = (rest[:cut.start()] if cut else rest).strip()
    tail = (rest[cut.start():] if cut else '').strip()
    type_text = re.sub(r'\s+(CHAR|BYTE)\s*$', '', type_text, flags=re.I)
    default = None
    default_match = re.search(r'DEFAULT\s+((?:\'[^\']*\'|[^\s,]+)(?:\s*\([^)]*\))?)', tail, re.I)
    if default_match:
        default = default_match.group(1)
    inline_pk = bool(re.search(r'PRIMARY\s+KEY', tail, re.I))
    unique = bool(re.search(r'\bUNIQUE\b', tail, re.I))
    not_null = bool(re.search(r'NOT\s+NULL', tail, re.I))
    references = ''
    reference_match = re.search(r'REFERENCES\s+([A-Za-z0-9_$#"]+)\s*(\([^)]*\))?', tail, re.I)
    if reference_match:
        target = _identifier(reference_match.group(1))[0]
        columns = reference_match.group(2) or ''
        references = f' REFERENCES "{target}"{columns}'
    check = ''
    check_match = re.search(r'CHECK\s*(\(.*\))', tail, re.I | re.S)
    if check_match:
        check = f' CHECK {check_match.group(1)}'

    sqlite_type = _sqlite_type(type_text)
    pieces = [f'"{name}" {sqlite_type}']
    if default is not None:
        pieces.append(f'DEFAULT {default}')
    if not_null:
        pieces.append('NOT NULL')
    if inline_pk:
        pieces.append('PRIMARY KEY')
    if unique:
        pieces.append('UNIQUE')
    pieces.append(references + check)
    return {
        'name': name, 'quoted': quoted, 'oracle_type': type_text.upper() or sqlite_type,
        'sqlite_type': sqlite_type, 'nullable': not not_null, 'default': default,
        'identity': identity, 'inline_pk': inline_pk, 'unique': unique,
        'references': references.strip(), 'check': check.strip(), 'ddl': ' '.join(p for p in pieces if p),
    }


def _translate_constraint(part):
    text = re.sub(r'\s+', ' ', part).strip()
    text = re.sub(r'\s+(ENABLE|DISABLE)(\s+(NOVALIDATE|VALIDATE))?$', '', text, flags=re.I)
    text = re.sub(r'\s+USING\s+INDEX.*$', '', text, flags=re.I)
    text = re.sub(r'\s+DEFERRABLE.*$', '', text, flags=re.I)
    return text


def _create_table(sql):
    match = re.match(
        r'CREATE\s+(OR\s+REPLACE\s+)?(GLOBAL\s+TEMPORARY\s+|PRIVATE\s+TEMPORARY\s+)?TABLE\s+'
        r'([A-Za-z0-9_$#"]+)\s*\((.*)\)\s*(TABLESPACE\s+\S+)?\s*$', sql, re.I | re.S)
    if not match:
        return sql
    table = _identifier(match.group(3))[0]
    body = match.group(4)
    columns = []
    constraints = []
    for part in _split_top_level(body):
        first = part.split()[0].upper().strip('(')
        if first in {'CONSTRAINT', 'PRIMARY', 'UNIQUE', 'CHECK', 'FOREIGN'}:
            constraints.append(_translate_constraint(part))
        else:
            columns.append(_column_definition(part))

    identity = next((column for column in columns if column['identity']), None)
    table_pk = ''
    for item in constraints:
        found = re.search(r'PRIMARY\s+KEY\s*\(([^)]*)\)', item, re.I)
        if found:
            table_pk = found.group(0)
            break
    pk_columns = re.findall(r'[A-Za-z0-9_$#"]+', table_pk[table_pk.find('('):]) if table_pk else []
    pk_names = [_identifier(name)[0] for name in pk_columns]

    if identity and pk_names in ([], [identity['name']]):
        # an identity column has to own the rowid, or the numbers never advance
        identity['ddl'] = f'"{identity["name"]}" INTEGER PRIMARY KEY AUTOINCREMENT'
        constraints = [item for item in constraints
                       if not re.search(r'PRIMARY\s+KEY', item, re.I)]

    pieces = [column['ddl'] for column in columns] + constraints
    return f'CREATE TABLE "{table}" (\n  ' + ',\n  '.join(pieces) + '\n)'


def _create_view(sql):
    match = re.match(r'CREATE\s+(OR\s+REPLACE\s+)?(FORCE\s+)?VIEW\s+([A-Za-z0-9_$#"]+)\s+(AS\s+.*)$',
                     sql, re.I | re.S)
    if not match:
        return sql
    name = _identifier(match.group(3))[0]
    body, _ = translate(match.group(4))
    return f'CREATE VIEW "{name}" {body}'


def _create_index(sql):
    match = re.match(r'CREATE\s+(UNIQUE\s+)?(BITMAP\s+)?INDEX\s+([A-Za-z0-9_$#"]+)\s+ON\s+'
                     r'([A-Za-z0-9_$#"]+)\s*(\(.*\))\s*$', sql, re.I | re.S)
    if not match:
        return sql
    unique = 'UNIQUE ' if match.group(1) else ''
    index = _identifier(match.group(3))[0]
    table = _identifier(match.group(4))[0]
    return f'CREATE {unique}INDEX "{index}" ON "{table}" {match.group(5)}'


# ---------------------------------------------------------------------------
# sequences
# ---------------------------------------------------------------------------
def _sequence_row(connection, name):
    return connection.execute(
        'SELECT name, current_value, increment_by FROM _sequence WHERE name = ?',
        (name.upper(),)).fetchone()


def _next_value(name):
    with _connect() as connection:
        _meta(connection)
        row = _sequence_row(connection, name)
        if not row:
            raise OracleError('ORA-02289', 'sequence does not exist')
        value = (row['current_value'] or 0) + (row['increment_by'] or 1)
        connection.execute('UPDATE _sequence SET current_value = ? WHERE name = ?',
                           (value, row['name']))
        connection.commit()
        return value


def _current_value(name):
    with _connect() as connection:
        _meta(connection)
        row = _sequence_row(connection, name)
        if not row or row['current_value'] is None:
            raise OracleError('ORA-08002', f'sequence {name.upper()}.CURRVAL is not yet defined in this session')
        return row['current_value']


# ---------------------------------------------------------------------------
# errors
# ---------------------------------------------------------------------------
class OracleError(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(f'{code}: {message}')

    def text(self):
        return f'{self.code}: {self.message}'


def _ora_error(error):
    """Map a SQLite complaint onto the Oracle message a DBA would recognise."""
    text = str(error).strip()
    lowered = text.lower()
    if 'no such table' in lowered:
        name = text.split(':', 1)[-1].strip()
        return OracleError('ORA-00942', 'table or view does not exist')
    if 'no such view' in lowered:
        return OracleError('ORA-00942', 'table or view does not exist')
    if 'no such column' in lowered:
        name = text.split(':', 1)[-1].strip()
        return OracleError('ORA-00904', f'"{name.upper()}": invalid identifier')
    if 'no such function' in lowered:
        name = text.split(':', 1)[-1].strip()
        return OracleError('ORA-00904', f'"{name.upper()}": invalid identifier')
    if 'already exists' in lowered:
        name = text.split(':', 1)[-1].strip()
        return OracleError('ORA-00955', f'name is already used by an existing object ({name.upper()})')
    if 'unique constraint failed' in lowered:
        target = text.split(':', 1)[-1].strip().upper().replace('.', '.')
        return OracleError('ORA-00001', f'unique constraint ({USER}.{target}) violated')
    if 'not null constraint failed' in lowered:
        target = text.split(':', 1)[-1].strip().upper().split('.')
        column = target[-1] if target else '?'
        table = target[-2] if len(target) > 1 else '?'
        return OracleError('ORA-01400', f'cannot insert NULL into ("{USER}"."{table}"."{column}")')
    if 'foreign key constraint failed' in lowered:
        return OracleError('ORA-02291', 'integrity constraint violated - parent key not found')
    if 'check constraint failed' in lowered:
        return OracleError('ORA-02290', 'check constraint violated')
    if 'no such index' in lowered:
        return OracleError('ORA-01418', 'specified index does not exist')
    if 'ambiguous column name' in lowered:
        return OracleError('ORA-00918', 'column ambiguously defined')
    if 'datatype mismatch' in lowered:
        return OracleError('ORA-01722', 'invalid number')
    if 'syntax error' in lowered or 'incomplete input' in lowered or 'near "' in lowered:
        return OracleError('ORA-00933', 'SQL command not properly ended')
    return OracleError('ORA-00900', text)


# ---------------------------------------------------------------------------
# execution
# ---------------------------------------------------------------------------
def _execute(connection, sql):
    """Run one translated statement, handling the objects SQLite lacks natively."""
    verb = _verb(sql)
    if verb == 'COMMENT':
        return _comment(connection, sql)
    if re.match(r'CREATE\s+(OR\s+REPLACE\s+)?SEQUENCE\b', sql, re.I):
        return _create_sequence(connection, sql)
    if re.match(r'DROP\s+SEQUENCE\b', sql, re.I):
        name = _identifier(sql.split()[2])[0]
        connection.execute('DELETE FROM _sequence WHERE name = ?', (name,))
        return {'message': 'Sequence dropped.', 'affected': 0, 'kind': 'ddl'}
    if verb == 'TRUNCATE':
        table = re.match(r'TRUNCATE\s+TABLE\s+([A-Za-z0-9_$#"]+)', sql, re.I)
        if table:
            name = _identifier(table.group(1))[0]
            connection.execute(f'DELETE FROM "{name}"')
            return {'message': 'Table truncated.', 'affected': 0, 'kind': 'ddl'}
    if verb == 'DESCRIBE':
        return None
    cursor = connection.execute(sql)
    if cursor.description:
        return {'cursor': cursor, 'kind': 'query'}
    affected = cursor.rowcount if cursor.rowcount is not None and cursor.rowcount >= 0 else 0
    return {'affected': affected, 'kind': 'dml'}


def _create_sequence(connection, sql):
    match = re.match(r'CREATE\s+(OR\s+REPLACE\s+)?SEQUENCE\s+([A-Za-z0-9_$#"]+)(.*)$', sql, re.I | re.S)
    if not match:
        raise OracleError('ORA-00933', 'SQL command not properly ended')
    name = _identifier(match.group(2))[0]
    tail = match.group(3) or ''
    start = re.search(r'START\s+WITH\s+(-?\d+)', tail, re.I)
    increment = re.search(r'INCREMENT\s+BY\s+(-?\d+)', tail, re.I)
    start_value = int(start.group(1)) if start else 1
    step = int(increment.group(1)) if increment else 1
    current = start_value - step if start_value != 1 or step != 1 else 0
    connection.execute(
        'INSERT OR REPLACE INTO _sequence (name, current_value, increment_by) VALUES (?, ?, ?)',
        (name, current, step))
    return {'message': 'Sequence created.', 'affected': 0, 'kind': 'ddl'}


def _comment(connection, sql):
    match = re.match(r"COMMENT\s+ON\s+(TABLE|COLUMN)\s+([A-Za-z0-9_$#.\"]+)\s+IS\s+'(.*)'\s*$",
                     sql, re.I | re.S)
    if not match:
        raise OracleError('ORA-00933', 'SQL command not properly ended')
    kind = match.group(1).upper()
    target = match.group(2)
    text = match.group(3).replace("''", "'")
    if kind == 'COLUMN':
        table, _, column = target.partition('.')
        connection.execute(
            'INSERT OR REPLACE INTO _comment (object_type, object_name, column_name, text) '
            'VALUES (?, ?, ?, ?)',
            ('COLUMN', _identifier(table)[0], _identifier(column)[0], text))
    else:
        connection.execute(
            'INSERT OR REPLACE INTO _comment (object_type, object_name, column_name, text) '
            'VALUES (?, ?, ?, ?)', ('TABLE', _identifier(target)[0], '', text))
    return {'message': 'Comment created.', 'affected': 0, 'kind': 'ddl'}


def _remember_columns(connection, sql):
    """Record the Oracle types of a freshly created table, for DESCRIBE."""
    match = re.match(r'CREATE\s+(OR\s+REPLACE\s+)?(TEMPORARY\s+)?TABLE\s+([A-Za-z0-9_$#"]+)\s*\((.*)\)',
                     sql, re.I | re.S)
    if not match:
        return
    table = _identifier(match.group(3))[0]
    position = 0
    for part in _split_top_level(match.group(4)):
        first = part.split()[0].upper().strip('(')
        if first in {'CONSTRAINT', 'PRIMARY', 'UNIQUE', 'CHECK', 'FOREIGN'}:
            continue
        position += 1
        column = _column_definition(part)
        connection.execute(
            'INSERT OR REPLACE INTO _column '
            '(table_name, column_name, oracle_type, sqlite_type, nullable, position, default_value) '
            'VALUES (?, ?, ?, ?, ?, ?, ?)',
            (table, column['name'], column['oracle_type'], column['sqlite_type'],
             1 if column['nullable'] else 0, position, column['default']))
    existing = connection.execute(
        'SELECT 1 FROM _comment WHERE object_type = ? AND object_name = ?', ('TABLE', table)).fetchone()
    if not existing:
        connection.execute(
            'INSERT OR REPLACE INTO _comment (object_type, object_name, column_name, text) '
            'VALUES (?, ?, ?, ?)', ('TABLE', table, '', ''))


def _drop_metadata(connection, sql):
    match = re.match(r'DROP\s+(TABLE|VIEW|INDEX)\s+([A-Za-z0-9_$#"]+)', sql, re.I)
    if not match:
        return
    kind = match.group(1).upper()
    name = _identifier(match.group(2))[0]
    if kind == 'TABLE':
        connection.execute('DELETE FROM _column WHERE table_name = ?', (name,))
        connection.execute('DELETE FROM _comment WHERE object_name = ?', (name,))
    if kind == 'VIEW':
        connection.execute('DELETE FROM _comment WHERE object_name = ?', (name,))


def _grid(rows, columns, elapsed):
    hidden = {'PASSWORD_HASH', 'PHOTO_URL'}
    values = [[row[column] for column in columns] for row in rows]
    numeric = []
    for position, column in enumerate(columns):
        found = False
        if column.upper() not in hidden:
            for row in values:
                value = row[position]
                if value is None:
                    continue
                found = isinstance(value, (int, float)) and not isinstance(value, bool)
                break
        numeric.append(found)
    cells = []
    for number, row in enumerate(values[:MAX_ROWS], start=1):
        line = []
        for position, value in enumerate(row):
            if columns[position].upper() in hidden:
                line.append({'text': PLACEHOLDER, 'null': False, 'numeric': False})
            else:
                line.append(_cell(value))
        cells.append({'number': number, 'cells': line})
    return {
        'columns': [{'name': _upper_name(column), 'numeric': numeric[position]}
                    for position, column in enumerate(columns)],
        'rows': cells,
        'row_count': len(values),
        'shown': len(cells),
        'truncated': max(len(values) - len(cells), 0),
        'elapsed_ms': elapsed,
    }


def column_label(name):
    """The Oracle name of a column in the practice schema (identifiers fold up)."""
    return _upper_name(name)


def pseudocolumn_label(name, user=None):
    """Name an engine expression the way Oracle would, without changing case.

    The portal keeps its own column names (`roll_no` stays `roll_no`); only the
    spellings the translator invented — datetime('now'), 'PORTAL' — are renamed.
    """
    text = (name or '').strip()
    if text.startswith("datetime('now')") or text.startswith('CURRENT_TIMESTAMP'):
        return 'SYSDATE'
    if text.startswith("date('now')"):
        return 'CURRENT_DATE'
    if len(text) >= 2 and text[0] == text[-1] == "'":
        literal = text[1:-1]
        if user and literal == user:
            return 'USER'
        if literal in {USER, 'PORTAL'}:
            return 'USER'
    return name


def _upper_name(name):
    """Oracle folds unquoted identifiers to upper case; a quoted mixed-case one survives."""
    if name == "'STUDIO'":
        return 'USER'
    if (name or '').startswith("datetime('now')"):
        return 'SYSDATE'
    if (name or '').startswith("date('now')"):
        return 'CURRENT_DATE'
    if re.fullmatch(r'-?\d+', name or ''):
        return 'NEXTVAL'
    if re.fullmatch(r'[a-z_][a-z0-9_]*', name or ''):
        return name.upper()
    return name


def _cell(value):
    if value is None:
        return {'text': 'NULL', 'null': True, 'numeric': False}
    if isinstance(value, bool):
        return {'text': 'TRUE' if value else 'FALSE', 'null': False, 'numeric': False}
    if isinstance(value, (int, float)):
        text = str(value) if isinstance(value, int) else f'{value:g}'
        return {'text': text, 'null': False, 'numeric': True}
    text = str(value)
    if len(text) > MAX_CELL:
        text = text[:MAX_CELL - 1] + '…'
    return {'text': text, 'null': False, 'numeric': False}


def run(sql, seeding=False):
    """Execute one Oracle statement against the practice schema."""
    ensure_schema(seeding=seeding)
    if re.match(r'\s*(BEGIN|DECLARE)\b', sql or '', re.I):
        return {'ok': False, 'statement': sql, 'verb': (sql or '').split()[0].upper(),
                'connection': 'oracle', 'code': 'ORA-00933', 'elapsed_ms': 0,
                'error': 'Anonymous PL/SQL blocks are not available in this simulation.',
                'hint': ('Run the statements one at a time, or read the same logic as a stored '
                         'program on the Database workshop page and in db/.')}
    statement, error = clean(sql)
    if error:
        return {'ok': False, 'statement': sql, 'error': error, 'code': 'ORA-00900',
                'connection': 'oracle', 'elapsed_ms': 0, 'verb': ''}

    verb = _verb(statement)
    base = {'statement': statement, 'verb': verb, 'connection': 'oracle'}

    upper = re.sub(r'--[^\n]*', ' ', statement).upper()
    for token, (code, message, hint) in _UNSUPPORTED.items():
        if re.search(rf'\b{token}\b', upper):
            return {**base, 'ok': False, 'code': code, 'error': message, 'hint': hint,
                    'elapsed_ms': 0}

    if verb in {'ATTACH', 'DETACH', 'PRAGMA', 'VACUUM', 'REINDEX'}:
        return {**base, 'ok': False, 'code': 'ORA-01031', 'elapsed_ms': 0,
                'error': (f'insufficient privileges — {verb} is not available in a practice '
                          'schema. The simulator keeps its file to itself.')}
    if verb in {'CREATE'} and re.search(r'\b(TRIGGER|PROCEDURE|FUNCTION|PACKAGE|TYPE|JAVA)\b', upper):
        return {**base, 'ok': False, 'code': 'ORA-00933', 'elapsed_ms': 0,
                'error': 'PL/SQL program units are not available in this simulation.',
                'hint': ('The portal\'s own procedures, functions and triggers are written in '
                         'both dialects in db/ and walked through on the Database workshop page.')}
    if verb in {'BEGIN', 'DECLARE'}:
        return {**base, 'ok': False, 'code': 'ORA-00933', 'elapsed_ms': 0,
                'error': 'Anonymous PL/SQL blocks are not available in this simulation.',
                'hint': ('Run the statements one at a time; the workshop page shows the same '
                         'logic as a stored program.')}
    if verb in {'COMMIT', 'ROLLBACK', 'SAVEPOINT'}:
        return {**base, 'ok': False, 'code': 'ORA-01086', 'elapsed_ms': 0,
                'error': f'{verb} has nothing to end: every statement in this session is committed as it runs.'}
    if verb in {'EXPLAIN'} and not re.match(r'EXPLAIN\s+PLAN', statement, re.I):
        return {**base, 'ok': False, 'code': 'ORA-00900', 'elapsed_ms': 0,
                'error': 'Use EXPLAIN PLAN FOR <statement>, or press F10.'}

    started = time.perf_counter()
    journaled = False
    if not seeding and verb in _WRITABLE:
        _journal_record(statement, verb)
        journaled = verb in _WRITABLE and journal_state()['can_undo']
    try:
        if verb == 'DESCRIBE':
            return _describe_result(statement, base, started)

        if re.match(r'EXPLAIN\s+PLAN\s+FOR\b', statement, re.I):
            inner = re.sub(r'^EXPLAIN\s+PLAN\s+FOR\s+', '', statement, flags=re.I)
            translated, notes = translate(inner)
            plan = _plan(translated)
            elapsed = round((time.perf_counter() - started) * 1000, 1)
            return {**base, 'ok': True, 'kind': 'plan', 'translated': translated,
                    'notes': notes, 'elapsed_ms': elapsed, **plan}

        translated, notes = translate(statement)
        with _connect() as connection:
            _meta(connection)
            if re.match(r'CREATE\s+(OR\s+REPLACE\s+)?(GLOBAL\s+TEMPORARY\s+)?TABLE\b', statement, re.I):
                _remember_columns(connection, statement)
            if re.match(r'DROP\s+(TABLE|VIEW|INDEX)\b', statement, re.I):
                _drop_metadata(connection, translated or statement)
            if translated is None:
                raise OracleError('ORA-00933', 'SQL command not properly ended')
            outcome = _execute(connection, translated) or {'kind': 'ddl', 'message': 'Completed.'}
            elapsed = round((time.perf_counter() - started) * 1000, 1)
            if outcome.get('kind') == 'query':
                cursor = outcome['cursor']
                rows = cursor.fetchall()
                columns = [item[0] for item in (cursor.description or [])]
                payload = _grid(rows, columns, elapsed)
                connection.commit()
                return {**base, 'ok': True, 'kind': 'read', 'translated': translated,
                        'notes': notes, **payload,
                        'message': f'{payload["row_count"]:,} row'
                                   f'{"" if payload["row_count"] == 1 else "s"} selected.'}
            connection.commit()
            message = outcome.get('message') or _default_message(
                verb, outcome.get('affected', 0), statement)
            structure = verb in {'CREATE', 'DROP', 'ALTER', 'TRUNCATE', 'COMMENT', 'RENAME'}
            return {**base, 'ok': True, 'kind': 'ddl' if structure else 'write',
                    'translated': translated, 'notes': notes, 'message': message,
                    'elapsed_ms': elapsed, 'affected': outcome.get('affected', 0),
                    'row_count': None, 'columns': [], 'rows': [], 'shown': 0, 'truncated': 0,
                    'journal': journal_state() if journaled else None}
    except OracleError as problem:
        if journaled:
            _journal_forget()
        elapsed = round((time.perf_counter() - started) * 1000, 1)
        return {**base, 'ok': False, 'code': problem.code,
                'error': problem.text(), 'elapsed_ms': elapsed}
    except sqlite3.Error as problem:
        if journaled:
            _journal_forget()
        elapsed = round((time.perf_counter() - started) * 1000, 1)
        mapped = _ora_error(problem)
        return {**base, 'ok': False, 'code': mapped.code,
                'error': mapped.text(), 'elapsed_ms': elapsed}


def _object_word(sql):
    """What DDL actually touched, so the message reads like SQL*Plus."""
    upper = sql.upper()
    for word, label in (('TABLE', 'Table'), ('VIEW', 'View'), ('INDEX', 'Index'),
                        ('SEQUENCE', 'Sequence'), ('COMMENT', 'Comment')):
        if re.search(rf'\b{word}\b', upper):
            return label
    return 'Object'


def _default_message(verb, affected, statement=''):
    if verb == 'INSERT':
        return f'{affected:,} row{"" if affected == 1 else "s"} created.'
    if verb == 'UPDATE':
        return f'{affected:,} row{"" if affected == 1 else "s"} updated.'
    if verb == 'DELETE':
        return f'{affected:,} row{"" if affected == 1 else "s"} deleted.'
    if verb == 'CREATE':
        return f'{_object_word(statement)} created.'
    if verb == 'DROP':
        return f'{_object_word(statement)} dropped.'
    if verb == 'COMMENT':
        return 'Comment created.'
    if verb == 'TRUNCATE':
        return 'Table truncated.'
    if verb == 'ALTER':
        return 'Table altered.'
    return 'Statement completed.'


def _describe_result(statement, base, started):
    name = re.sub(r'^(DESCRIBE|DESC)\s+', '', statement, flags=re.I).strip().strip(';')
    details = describe(name)
    if not details.get('ok'):
        raise OracleError('ORA-00942', 'table or view does not exist')
    rows = []
    for position, column in enumerate(details['columns'], start=1):
        rows.append({'number': position, 'cells': [
            {'text': column['name'], 'null': False, 'numeric': False},
            {'text': 'NOT NULL' if not column['nullable'] else '', 'null': False, 'numeric': False},
            {'text': column['type'], 'null': False, 'numeric': False},
        ]})
    elapsed = round((time.perf_counter() - started) * 1000, 1)
    return {**base, 'ok': True, 'kind': 'describe', 'elapsed_ms': elapsed,
            'columns': [{'name': 'Name', 'numeric': False},
                        {'name': 'Null?', 'numeric': False},
                        {'name': 'Type', 'numeric': False}],
            'rows': rows, 'row_count': len(rows), 'shown': len(rows), 'truncated': 0,
            'message': f'{len(rows)} column{"" if len(rows) == 1 else "s"}.'}


def _plan(sql):
    rows = []
    try:
        with _connect() as connection:
            cursor = connection.execute('EXPLAIN QUERY PLAN ' + sql)
            for row in cursor.fetchall():
                detail = str(row['detail'] if 'detail' in row.keys() else row[3])
                lowered = detail.lower()
                kind = 'scan' if ('scan' in lowered and 'search' not in lowered) else (
                    'index' if ('search' in lowered or 'index' in lowered) else 'other')
                rows.append({'detail': detail, 'kind': kind})
    except sqlite3.Error as problem:
        raise OracleError('ORA-00933', 'SQL command not properly ended')
    scans = [row for row in rows if row['kind'] == 'scan']
    return {
        'rows': [], 'columns': [], 'shown': 0, 'truncated': 0, 'row_count': 0,
        'nodes': rows, 'verdict': 'scan' if scans else 'index',
        'summary': f'{len(scans)} full table scan{"" if len(scans) == 1 else "s"} in {len(rows)} step{"" if len(rows) == 1 else "s"}.',
    }


def run_script(text):
    """Run a whole SQL*Plus script, one statement at a time."""
    ensure_schema()
    statements = split_script(text)
    if not statements:
        return {'ok': False, 'statements': [], 'error': (
            'There is nothing to run: the editor is empty, or holds only comments.')}
    results = []
    for position, item in enumerate(statements, start=1):
        outcome = run(item['sql'])
        outcome['index'] = position
        results.append(outcome)
    failed = [item for item in results if not item['ok']]
    return {
        'ok': not failed, 'statements': results, 'total': len(results),
        'succeeded': len(results) - len(failed), 'failed': len(failed),
        'elapsed_ms': round(sum(item.get('elapsed_ms') or 0 for item in results), 1),
    }


def explain(sql):
    """The plan for an Oracle statement, expressed the way the client shows it."""
    statement, error = clean(sql)
    if error:
        return {'ok': False, 'error': error, 'code': 'ORA-00900', 'nodes': []}
    try:
        translated, notes = translate(statement)
        plan = _plan(translated)
        return {'ok': True, 'statement': statement, 'translated': translated,
                'notes': notes, 'nodes': plan['nodes'], 'verdict': plan['verdict'],
                'summary': plan['summary'], 'elapsed_ms': 0}
    except OracleError as problem:
        return {'ok': False, 'code': problem.code, 'error': problem.text(), 'nodes': []}
    except Exception as problem:                       # pragma: no cover - defensive
        return {'ok': False, 'code': 'ORA-00900', 'error': str(problem), 'nodes': []}


# ---------------------------------------------------------------------------
# the catalogue behind the navigator
# ---------------------------------------------------------------------------
def catalogue():
    ensure_schema()
    result = {'tables': [], 'views': [], 'indexes': [], 'sequences': []}
    with _connect() as connection:
        _meta(connection)
        objects = connection.execute(
            "SELECT name, type FROM sqlite_master WHERE type IN ('table','view','index') "
            "AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '\\_%' ESCAPE '\\' "
            "ORDER BY type, name").fetchall()
        comments = {(row['object_name'], row['column_name']): row['text']
                    for row in connection.execute('SELECT * FROM _comment')}
        stored = {(row['table_name'], row['column_name']): row
                  for row in connection.execute('SELECT * FROM _column')}
        for row in objects:
            name = row['name']
            if row['type'] == 'index':
                if name.startswith('sqlite_'):
                    continue
                target = connection.execute(
                    "SELECT tbl_name FROM sqlite_master WHERE name = ?", (name,)).fetchone()
                columns = [item['name'] for item in connection.execute(
                    f'PRAGMA index_info("{name}")') if item['name']]
                result['indexes'].append({
                    'name': name, 'table': target['tbl_name'] if target else '',
                    'columns': columns})
                continue
            if row['type'] == 'table':
                columns = []
                for position, item in enumerate(connection.execute(f'PRAGMA table_info("{name}")'), start=1):
                    meta = stored.get((name, item['name'])) or stored.get((name, item['name'].upper()))
                    columns.append({
                        'name': item['name'],
                        'type': meta['oracle_type'] if meta else _oracle_type_name(item['type']),
                        'pk': bool(item['pk']),
                        'nullable': not item['notnull'],
                        'default': item['dflt_value'] or '',
                        'comment': comments.get((name, item['name']), ''),
                    })
                count = connection.execute(f'SELECT COUNT(*) AS n FROM "{name}"').fetchone()['n']
                result['tables'].append({
                    'name': name, 'rows': count, 'columns': columns,
                    'comment': comments.get((name, ''), ''),
                })
            else:
                columns = []
                try:
                    for item in connection.execute(f'PRAGMA table_info("{name}")'):
                        columns.append({'name': item['name'],
                                        'type': _oracle_type_name(item['type']),
                                        'pk': False, 'nullable': True, 'default': '',
                                        'comment': ''})
                except sqlite3.Error:
                    columns = []
                result['views'].append({
                    'name': name, 'rows': 0, 'columns': columns,
                    'comment': comments.get((name, ''), ''),
                })
        for row in connection.execute('SELECT name, current_value, increment_by FROM _sequence ORDER BY name'):
            current = row['current_value'] if row['current_value'] is not None else 0
            result['sequences'].append({
                'name': row['name'],
                'next': current + (row['increment_by'] or 1),
                'last': current or None,
                'increment': row['increment_by'],
            })
    return result


def _oracle_type_name(sqlite_type):
    mapping = {'TEXT': 'VARCHAR2(4000)', 'INTEGER': 'NUMBER', 'NUMERIC': 'NUMBER',
               'REAL': 'BINARY_DOUBLE', 'BLOB': 'BLOB', '': 'VARCHAR2(4000)'}
    return mapping.get((sqlite_type or '').upper(), (sqlite_type or 'VARCHAR2(4000)').upper())


def describe(name):
    target = (name or '').strip().strip('"')
    for entry in catalogue()['tables']:
        if entry['name'].upper() == target.upper():
            return {'ok': True, 'type': 'table', **entry}
    for entry in catalogue()['views']:
        if entry['name'].upper() == target.upper():
            return {'ok': True, 'type': 'view', **entry}
    return {'ok': False, 'error': f'ORA-00942: table or view does not exist ({target})'}


def connection():
    """The facts behind the connection selector and the About dialog."""
    ensure_schema()
    counts = {key: len(value) for key, value in catalogue().items()}
    size = 0
    try:
        size = os.path.getsize(path())
    except OSError:
        size = 0
    return {
        'name': CONNECTION_NAME, 'product': PRODUCT, 'user': USER,
        'engine': 'Oracle', 'version': '21c Express Edition (simulated)',
        'kind': 'simulated', 'dialect': 'Oracle Database 21c SQL',
        'banner': f'{PRODUCT} Release 21.0.0.0.0 (simulated)',
        'database': os.path.basename(path()), 'schema': USER,
        'size': f'{round(size / 1024, 1)} KB' if size else '0 KB',
        'read_only': False, 'mode': 'Practice schema · writable',
        'charset': 'AL32UTF8', 'page_size': '8192 bytes',
        'journal': 'Online redo (simulated)', 'foreign_keys': 'ENFORCED',
        'isolation': 'READ COMMITTED', 'autocommit': 'ON · each statement commits',
        'counts': counts, 'started': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
    }


STARTER = """-- ============================================================================
-- ORACLE_XE · Oracle Database 21c Express Edition (simulated)
--
-- A writable practice schema. CREATE, INSERT, UPDATE, DELETE, DROP and
-- TRUNCATE really happen here — and never touch the portal's own data.
--
--   F9 / Ctrl+Enter   run the statement under the cursor
--   F5                run the whole script
--   F10               EXPLAIN PLAN for the statement under the cursor
--
-- The classic SCOTT schema is already loaded: EMP, DEPT and EMP_SEQ.
--
-- Running this twice? The second CREATE reports ORA-00955, exactly as Oracle
-- would. Press "Reset practice schema" in the toolbar for a clean slate.
-- ============================================================================

SELECT USER, SYSDATE FROM dual;

SELECT empno, ename, job, sal, deptno
FROM emp
WHERE ROWNUM <= 5;

SELECT d.dname, COUNT(*) AS headcount, SUM(e.sal) AS payroll
FROM emp e
JOIN dept d ON d.deptno = e.deptno
GROUP BY d.dname
ORDER BY payroll DESC;

SELECT ename, sal, NVL(comm, 0) AS commission,
       DECODE(job, 'ANALYST', 'Technical', 'MANAGER', 'Leadership', 'Other') AS band
FROM emp
WHERE deptno = 20;

-- Create your own table the way Oracle expects:
CREATE TABLE project (
  project_id NUMBER(6) GENERATED BY DEFAULT AS IDENTITY,
  title      VARCHAR2(60) NOT NULL,
  started    DATE DEFAULT SYSDATE,
  budget     NUMBER(12,2),
  CONSTRAINT project_pk PRIMARY KEY (project_id)
);

INSERT INTO project (title, budget) VALUES ('Library automation', 250000);
INSERT INTO project (title, budget) VALUES ('Hostel wifi upgrade', 87500.50);

SELECT project_id, title, started, budget FROM project;

COMMENT ON TABLE project IS 'Practice table created from the studio.';
DESCRIBE project;
"""


SNIPPETS = [
    {'label': 'Describe a table (Oracle style)', 'sql': 'DESCRIBE emp;'},
    {'label': 'Create a table with an identity column', 'sql': (
        'CREATE TABLE student_note (\n'
        '  note_id   NUMBER(6) GENERATED BY DEFAULT AS IDENTITY,\n'
        '  roll_no   VARCHAR2(12) NOT NULL,\n'
        '  note      VARCHAR2(200),\n'
        '  added_on  DATE DEFAULT SYSDATE,\n'
        '  CONSTRAINT student_note_pk PRIMARY KEY (note_id)\n'
        ');')},
    {'label': 'Next value from a sequence', 'sql': 'SELECT emp_seq.NEXTVAL FROM dual;'},
    {'label': 'NVL, DECODE and ROWNUM together', 'sql': (
        "SELECT ename, NVL(comm, 0) AS commission,\n"
        "       DECODE(job, 'CLERK', 'Support', 'Manager', 'Leadership', 'Other') AS band\n"
        "FROM emp\nWHERE ROWNUM <= 6;")},
    {'label': 'Explain a plan', 'sql': (
        'EXPLAIN PLAN FOR\nSELECT d.dname, COUNT(*) AS headcount\n'
        'FROM emp e JOIN dept d ON d.deptno = e.deptno\nGROUP BY d.dname;')},
    {'label': 'Reset the practice schema', 'sql': 'DROP TABLE project CASCADE CONSTRAINTS PURGE;'},
]
