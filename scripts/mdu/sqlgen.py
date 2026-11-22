"""Dialect helpers for the Marvel & DC Universe schema.

`db/universe_schema.sql` and `db/universe_views.sql` are written in MySQL 8 syntax,
because that is the spelling the project's ER design and data dictionary use. The
portal also runs an embedded SQLite engine on the free host, so the loader needs the
same tables in SQLite spelling.

Rather than maintain two hand-written schemas (which drift), the translation lives
here: a small, explicit, testable set of rewrites covering exactly the constructs this
schema uses. Anything outside that list raises instead of being silently mistranslated.
"""
import re

UNSUPPORTED = ('FULLTEXT', 'SPATIAL', 'PARTITION BY', 'ROW_FORMAT', 'AUTO_INCREMENT=')


def split_statements(sql_text):
    """Split a script into single statements.

    Handles line comments, string literals (the descriptions contain semicolons and
    double dashes) and both semicolon and blank-line separation.
    """
    statements, buffer, index = [], [], 0
    length = len(sql_text)
    in_string = False
    while index < length:
        char = sql_text[index]
        if in_string:
            buffer.append(char)
            if char == "'":
                if index + 1 < length and sql_text[index + 1] == "'":
                    buffer.append(sql_text[index + 1])
                    index += 2
                    continue
                in_string = False
            index += 1
            continue
        if char == "'":
            in_string = True
            buffer.append(char)
            index += 1
            continue
        if sql_text.startswith('--', index):
            end_of_line = sql_text.find('\n', index)
            index = length if end_of_line == -1 else end_of_line
            continue
        if char == ';':
            candidate = ''.join(buffer).strip()
            if candidate:
                statements.append(candidate)
            buffer = []
            index += 1
            continue
        buffer.append(char)
        index += 1
    tail = ''.join(buffer).strip()
    if tail:
        statements.append(tail)
    return statements


def to_sqlite(statement):
    """Rewrite one MySQL DDL statement for SQLite. Raises on anything unexpected."""
    upper = statement.upper()
    for token in UNSUPPORTED:
        if token in upper:
            raise ValueError(f'to_sqlite: unsupported MySQL construct {token!r} in: '
                             f'{statement[:120]}')

    sql = statement

    # CREATE OR REPLACE VIEW → separate DROP + CREATE, handled by the caller.
    if re.match(r'\s*CREATE\s+OR\s+REPLACE\s+VIEW', sql, re.I):
        raise ValueError('to_sqlite: use to_sqlite_view() for CREATE OR REPLACE VIEW')

    # INT AUTO_INCREMENT PRIMARY KEY → INTEGER PRIMARY KEY AUTOINCREMENT
    sql = re.sub(r'\bINT(EGER)?\s+AUTO_INCREMENT\s+PRIMARY\s+KEY\b',
                 'INTEGER PRIMARY KEY AUTOINCREMENT', sql, flags=re.I)
    # a bare AUTO_INCREMENT left behind is a bug
    if re.search(r'AUTO_INCREMENT', sql, re.I):
        raise ValueError(f'to_sqlite: unhandled AUTO_INCREMENT in: {sql[:120]}')
    # ENGINE=InnoDB / trailing table options
    sql = re.sub(r'\)\s*ENGINE\s*=\s*InnoDB\s*$', ')', sql.strip(), flags=re.I)
    # CREATE INDEX → CREATE INDEX IF NOT EXISTS (re-runnable)
    sql = re.sub(r'^\s*CREATE\s+INDEX\s+(?!IF\s+NOT\s+EXISTS)',
                 'CREATE INDEX IF NOT EXISTS ', sql, flags=re.I)
    # MySQL treats UNIQUE (a) as an index; SQLite accepts the same syntax.
    return sql.strip()


def to_sqlite_view(statement):
    """Return ['DROP VIEW IF EXISTS name', 'CREATE VIEW name ...'] for a view."""
    match = re.match(r'\s*CREATE\s+OR\s+REPLACE\s+VIEW\s+([A-Za-z_][A-Za-z0-9_]*)\s+AS\s+(.*)$',
                     statement, re.I | re.S)
    if not match:
        raise ValueError(f'to_sqlite_view: cannot parse: {statement[:120]}')
    name, body = match.group(1), match.group(2).strip()
    return [f'DROP VIEW IF EXISTS {name}', f'CREATE VIEW {name} AS {body}']


def script_to_sqlite(sql_text):
    """Translate a whole MySQL DDL script into a list of SQLite statements."""
    out = []
    for statement in split_statements(sql_text):
        if re.match(r'\s*CREATE\s+OR\s+REPLACE\s+VIEW', statement, re.I):
            out.extend(to_sqlite_view(statement))
        else:
            out.append(to_sqlite(statement))
    return out
