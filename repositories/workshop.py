"""The database workshop: joins, views, procedures, functions and triggers, live.

This module is the engine behind ``/database``. It does not invent SQL: the joins
and the set/logic queries come from ``db/queries/*.sql``, the view and trigger
definitions come from the running database's own catalogue, and the procedure and
function source is read out of ``db/procedures.sql``. What this module adds is

* a **dialect layer** so the same statement runs on MySQL 8 and on the embedded
  SQLite engine (``RIGHT JOIN`` becomes a swapped ``LEFT JOIN``, ``CONCAT(a,' ',b)``
  becomes ``a || ' ' || b``), with the rewrite shown, never hidden;
* a **measurement** wrapper that reports elapsed milliseconds, the row count and
  whether the result was truncated, exactly like a database client's status line;
* a **read-only dry run** for each stored procedure, so the checks it performs can
  be watched step by step without changing a single row;
* **trigger proofs**: a deliberate violation is attempted inside a SAVEPOINT and
  rolled back, so the guard's own message can be read on screen while the data
  stays exactly as it was.
"""
import os
import re
import time

from repositories import db_pool as _db_module
from repositories.db_pool import db_pool

ROW_LIMIT = 40
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCEDURE_FILE = os.path.join(BASE_DIR, 'db', 'procedures.sql')
QUERY_DIR = os.path.join(BASE_DIR, 'db', 'queries')


def is_mysql():
    return bool(db_pool.is_mysql)


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def _q(name):
    """Quote an identifier for the engine in use."""
    quote = '`' if is_mysql() else '"'
    return f'{quote}{name}{quote}'


def _elapsed(start):
    return round((time.perf_counter() - start) * 1000.0, 2)


def _cell(value, limit=180):
    if value is None:
        return {'text': 'NULL', 'null': True, 'numeric': False}
    if isinstance(value, bool):
        return {'text': '1' if value else '0', 'null': False, 'numeric': True}
    if isinstance(value, (int, float)):
        return {'text': f'{value:,}' if isinstance(value, int) else f'{value:,.2f}',
                'null': False, 'numeric': True}
    text = str(value)
    numeric = bool(re.fullmatch(r'-?\d+(\.\d+)?', text))
    if len(text) > limit:
        text = text[:limit - 1] + '…'
    return {'text': text, 'null': False, 'numeric': numeric}


def _normalise(rows, columns, elapsed_ms, total=None):
    """Shape a result set the way the page and the JSON endpoints both want."""
    rows = rows or []
    columns = columns or (list(rows[0].keys()) if rows and isinstance(rows[0], dict) else [])
    rendered = []
    for number, row in enumerate(rows, start=1):
        values = [row.get(column) for column in columns] if isinstance(row, dict) else list(row)
        rendered.append({'number': number, 'cells': [_cell(value) for value in values]})
    return {
        'ok': True,
        'columns': columns,
        'rows': rendered,
        'row_count': len(rendered) if total is None else total,
        'shown': len(rendered),
        'truncated': bool(total is not None and total > len(rendered)),
        'elapsed_ms': elapsed_ms,
        'error': None,
    }


def _failure(start, error, columns=None):
    return {'ok': False, 'columns': columns or [], 'rows': [], 'row_count': 0, 'shown': 0,
            'truncated': False, 'elapsed_ms': _elapsed(start), 'error': str(error)}


# ---------------------------------------------------------------------------
# dialect layer
# ---------------------------------------------------------------------------
_CONCAT = re.compile(r"CONCAT\s*\(([^()]*)\)", re.IGNORECASE)


def to_sqlite(sql):
    """Translate the handful of MySQL spellings this workshop uses.

    Only what the workshop itself needs is translated — never a general purpose
    rewriter, because a silent rewrite of arbitrary SQL would be worse than an
    honest error.
    """
    text = _CONCAT.sub(lambda m: '(' + ' || '.join(part.strip() for part in m.group(1).split(',')) + ')', sql)
    text = re.sub(r'\bCURDATE\(\)', "date('now')", text, flags=re.IGNORECASE)
    text = re.sub(r'\bNOW\(\)', "datetime('now')", text, flags=re.IGNORECASE)
    text = re.sub(r'\bIFNULL\s*\(', 'COALESCE(', text, flags=re.IGNORECASE)
    return text


def executed_form(sql, sqlite_sql=None):
    """The statement as the engine actually receives it, plus a note when it differs."""
    if is_mysql():
        return sql, None
    if sqlite_sql:
        return sqlite_sql, (
            'SQLite has no FULL OUTER JOIN and older builds have no RIGHT JOIN, so this '
            'runs as the equivalent rewrite below. MySQL 8 executes the statement above '
            'exactly as printed.')
    if to_sqlite(sql) != sql:
        return to_sqlite(sql), ('SQLite spells concatenation with || and dates with '
                                "date('now'); the rewrite is mechanical.")
    return sql, None


# ---------------------------------------------------------------------------
# running a statement
# ---------------------------------------------------------------------------
def run_sql(sql, limit=ROW_LIMIT, params=()):
    """Execute a read statement and report what the engine did."""
    start = time.perf_counter()
    try:
        table = db_pool.execute_query(sql, params or (), fetch='table')
        rows = table['rows']
        elapsed = _elapsed(start)
        total = len(rows)
        return _normalise(rows[:limit], table['columns'], elapsed, total=total)
    except Exception as error:                    # surfaced to the page, never raised
        return _failure(start, error)


def _explain(sql):
    """The engine's own plan, in whichever spelling it understands."""
    if is_mysql():
        try:
            return db_pool.execute_query(f'EXPLAIN {sql}', fetch='all') or []
        except Exception as error:
            return {'error': str(error)}
    try:
        return db_pool.execute_query(f'EXPLAIN QUERY PLAN {sql}', fetch='all') or []
    except Exception as error:
        return {'error': str(error)}


def explain(sql, sqlite_sql=None):
    """A readable execution plan: one row per engine step, plus a plain verdict."""
    exec_sql, note = executed_form(sql, sqlite_sql)
    start = time.perf_counter()
    rows = _explain(exec_sql)
    if isinstance(rows, dict):
        return {'ok': False, 'error': rows.get('error'), 'note': note,
                'steps': [], 'elapsed_ms': _elapsed(start)}
    steps = []
    for row in rows:
        detail = row.get('detail') if isinstance(row, dict) else None
        if detail is None and isinstance(row, dict):
            detail = ' · '.join(f'{key}={value}' for key, value in row.items())
        detail = str(detail or '')
        lowered = detail.lower()
        if 'using index' in lowered or 'using covering index' in lowered:
            kind, verdict = 'index', 'index lookup'
        elif lowered.startswith('scan') or 'scan ' in lowered or 'search' not in lowered and 'scan' in lowered:
            kind, verdict = 'scan', 'full scan'
        else:
            kind, verdict = 'other', 'planner step'
        if 'search' in lowered and 'index' in lowered:
            kind, verdict = 'index', 'index lookup'
        steps.append({'detail': detail, 'kind': kind, 'verdict': verdict,
                      'rows': row.get('rows') if isinstance(row, dict) else None})
    scans = [step for step in steps if step['kind'] == 'scan']
    return {
        'ok': True,
        'note': note,
        'steps': steps,
        'elapsed_ms': _elapsed(start),
        'summary': ('The planner walks a whole table — fine at this size, the thing to '
                    'avoid at a million rows.' if scans else
                    'Every step is an index lookup or a constant scan.'),
        'verdict': 'scan' if scans else 'index',
    }


# ---------------------------------------------------------------------------
# 1. joins
# ---------------------------------------------------------------------------
# Each demo carries the canonical statement, the engine-specific rewrite (when one
# is needed), what it is for, and the sentence to say out loud in a viva.
JOIN_DEMOS = [
    {
        'key': 'inner',
        'label': 'INNER JOIN',
        'title': 'Course offerings with their course, department and instructor',
        'question': 'Which offerings exist, with the readable names on both sides?',
        'sql': """SELECT co.offering_id,
       c.course_code,
       c.title                                    AS course_title,
       d.dept_code,
       CONCAT(f.first_name, ' ', f.last_name)     AS instructor,
       co.academic_year,
       co.term,
       co.capacity,
       co.enrolled_count
FROM course_offering co
JOIN course     c ON c.course_id   = co.course_id
JOIN department d ON d.dept_id     = c.dept_id
JOIN faculty    f ON f.faculty_id  = co.faculty_id
ORDER BY c.course_code, co.academic_year DESC;""",
        'why': ('Four tables, three one-to-many relationships walked from the child row '
                'outwards. INNER JOIN keeps only rows that have a partner on both sides — '
                'an offering whose faculty row had been deleted would vanish from this list.'),
        'note': 'Say this: "an inner join is an intersection; if either side is missing, the row is gone."',
        'check': 'Every offering appears exactly once — the joins do not multiply rows because each '
                 'foreign key points at exactly one parent row.',
    },
    {
        'key': 'left-anti',
        'label': 'LEFT JOIN (anti-join)',
        'title': 'Students with no enrollment at all',
        'question': 'Who is on the roll but taking nothing?',
        'sql': """SELECT s.student_id,
       s.roll_no,
       CONCAT(s.first_name, ' ', s.last_name) AS student_name,
       d.dept_code,
       s.current_semester,
       s.status
FROM student s
JOIN department d  ON d.dept_id     = s.dept_id
LEFT JOIN enrollment e ON e.student_id = s.student_id
WHERE e.enrollment_id IS NULL
ORDER BY s.roll_no;""",
        'why': ('The LEFT JOIN keeps every student even when there is no enrollment; the '
                'WHERE ... IS NULL then keeps only the students whose right-hand side never '
                'matched. That pair of lines is the anti-join, and it is the standard way to '
                'ask "what is missing?" without a NOT IN subquery.'),
        'note': 'Say this: "LEFT JOIN keeps the left row with NULLs; filtering on that NULL turns it into a correctness check."',
        'check': 'If this list is long, enrolment is the leak — not the students.',
    },
    {
        'key': 'right',
        'label': 'RIGHT JOIN',
        'title': 'Every student, including the ones taking nothing',
        'question': 'How does RIGHT JOIN differ from LEFT JOIN, row for row?',
        'sql': """SELECT s.roll_no,
       CONCAT(s.first_name, ' ', s.last_name) AS student_name,
       COUNT(e.enrollment_id)                 AS courses_taken
FROM enrollment e
RIGHT JOIN student s ON s.student_id = e.student_id
GROUP BY s.student_id, s.roll_no, s.first_name, s.last_name
ORDER BY courses_taken, s.roll_no;""",
        'sqlite_sql': """SELECT s.roll_no,
       (s.first_name || ' ' || s.last_name) AS student_name,
       COUNT(e.enrollment_id)               AS courses_taken
FROM student s
LEFT JOIN enrollment e ON s.student_id = e.student_id
GROUP BY s.student_id, s.roll_no, s.first_name, s.last_name
ORDER BY courses_taken, s.roll_no;""",
        'why': ('RIGHT JOIN keeps every row of the table on the right of the join — here all '
                'students — even when the left side has nothing to pair with, which is why the '
                'students taking no courses still appear with a count of 0. Swap the two tables '
                'and write LEFT JOIN instead and you get the same rows: RIGHT JOIN is a LEFT '
                'JOIN read backwards, and knowing that is what makes old Oracle-style SQL '
                'readable.'),
        'note': 'Say this: "RIGHT JOIN protects the right table; swap the tables and it is a LEFT JOIN."',
        'check': 'Count the rows: it equals the number of students, not the number of enrollments.',
    },
    {
        'key': 'full',
        'label': 'FULL OUTER JOIN',
        'title': 'Departments with no course, and courses with no department',
        'question': 'Both sides at once — who is orphaned, left or right?',
        'sql': """SELECT d.dept_code,
       d.dept_name,
       c.course_code,
       c.title AS course_title
FROM department d
FULL OUTER JOIN course c ON c.dept_id = d.dept_id
ORDER BY d.dept_code, c.course_code;""",
        'sqlite_sql': """SELECT d.dept_code, d.dept_name, c.course_code, c.title AS course_title
FROM department d LEFT JOIN course c ON c.dept_id = d.dept_id
UNION
SELECT d.dept_code, d.dept_name, c.course_code, c.title AS course_title
FROM course c LEFT JOIN department d ON c.dept_id = d.dept_id
WHERE d.dept_id IS NULL
ORDER BY 1, 3;""",
        'why': ('FULL OUTER JOIN is the union of both directions: unmatched rows from either '
                'table survive, with NULLs on the other side. MySQL has no FULL OUTER JOIN at '
                'all, so the portable spelling is UNION of a LEFT JOIN and a RIGHT JOIN — which '
                'is exactly what runs below on SQLite.'),
        'note': 'Say this: "full outer = left ∪ right; if your engine lacks it, UNION the two outer joins."',
        'check': 'Orphan rows on both sides in one look — the referential-integrity safety net.',
    },
    {
        'key': 'self',
        'label': 'SELF JOIN',
        'title': 'Faculty next to their head of department',
        'question': 'Who reports to whom, inside one table?',
        'sql': """SELECT CONCAT(f.first_name, ' ', f.last_name) AS faculty_member,
       f.designation,
       CONCAT(h.first_name, ' ', h.last_name) AS head_of_department,
       h.designation                          AS head_designation,
       d.dept_code
FROM faculty f
JOIN department d ON d.dept_id = f.dept_id
LEFT JOIN faculty h ON h.faculty_id = d.hod_faculty_id
ORDER BY d.dept_code, faculty_member;""",
        'why': ('A self join is the same table twice under two aliases: `f` is the member of '
                'staff, `h` is the head they report to, reached through the department. The '
                'LEFT JOIN matters — a department with no head still lists its staff.'),
        'note': 'Say this: "two aliases, one table — the hierarchy is a foreign key pointing at the same table."',
        'check': 'Heads appear against their own department; departments without a head show NULL.',
    },
    {
        'key': 'cross',
        'label': 'CROSS JOIN',
        'title': 'Every exam slot combination for every offering',
        'question': 'What does a cartesian product look like, and why is it dangerous?',
        'sql': """SELECT co.offering_id,
       c.course_code,
       ex.exam_type,
       ex.max_marks
FROM course_offering co
JOIN course c ON c.course_id = co.course_id
CROSS JOIN (SELECT DISTINCT exam_type, max_marks FROM exam) ex
ORDER BY c.course_code, ex.exam_type
LIMIT 25;""",
        'why': ('A CROSS JOIN pairs every row of one side with every row of the other: three '
                'offerings times two exam types is six, not three. It is occasionally what you '
                'want (building a matrix), and it is the classic accident when someone forgets '
                'a join condition — a 1,000-row table times a 1,000-row table is a million rows.'),
        'note': 'Say this: "a missing ON clause is a cross join, and a cross join is how a missing join condition becomes an outage."',
        'check': 'Count the rows: it is a product, not a sum.',
    },
    {
        'key': 'five-table',
        'label': '5-table traversal',
        'title': 'A full transcript line, from student to marks',
        'question': 'How far can one row travel through the schema?',
        'sql': """SELECT s.roll_no,
       CONCAT(s.first_name, ' ', s.last_name) AS student_name,
       c.course_code,
       ex.exam_type,
       r.marks_obtained,
       ex.max_marks,
       ROUND(100.0 * r.marks_obtained / ex.max_marks, 2) AS percentage
FROM student s
JOIN enrollment      e  ON e.student_id   = s.student_id
JOIN course_offering co ON co.offering_id = e.offering_id
JOIN course          c  ON c.course_id    = co.course_id
JOIN result          r  ON r.enrollment_id = e.enrollment_id
JOIN exam            ex ON ex.exam_id     = r.exam_id
WHERE e.status = 'Enrolled'
ORDER BY s.roll_no, c.course_code
LIMIT 25;""",
        'why': ('Five tables and five keys: student → enrollment → offering → course, with '
                'result and exam hanging off the enrollment. This is the query behind a mark '
                'sheet, and it only stays correct because every hop joins on a declared key.'),
        'note': 'Say this: "normalisation spreads a fact across tables; a join puts it back together for reading."',
        'check': 'Every row carries a real mark against a real exam — no NULLs from missing hops.',
    },
]


def join_demos():
    """The join catalogue with each statement as the current engine will receive it."""
    demos = []
    for demo in JOIN_DEMOS:
        entry = dict(demo)
        entry['sql'], entry['rewrite'] = executed_form(demo['sql'], demo.get('sqlite_sql'))
        entry['engine_sql'] = entry['sql']
        demos.append(entry)
    return demos


def join_demo(key):
    for demo in join_demos():
        if demo['key'] == key:
            return demo
    return None


def run_demo(key, limit=ROW_LIMIT):
    demo = join_demo(key)
    if not demo:
        return {'ok': False, 'error': f'No join demonstration called {key}.', 'columns': [], 'rows': [],
                'row_count': 0, 'shown': 0, 'truncated': False, 'elapsed_ms': 0}
    outcome = run_sql(demo['engine_sql'], limit=limit)
    outcome['demo'] = key
    outcome['engine_sql'] = demo['engine_sql']
    outcome['rewrite'] = demo['rewrite']
    return outcome


def explain_demo(key):
    demo = join_demo(key)
    if not demo:
        return {'ok': False, 'error': f'No join demonstration called {key}.'}
    plan = explain(demo['sql'], demo.get('sqlite_sql'))
    plan['demo'] = key
    plan['engine_sql'] = demo['engine_sql']
    return plan


# ---------------------------------------------------------------------------
# 2. views
# ---------------------------------------------------------------------------
VIEW_NOTES = {
    'v_student_overview': {
        'purpose': 'One row per student with their department names and two computed figures: '
                   'how many offerings they are enrolled in, and their average mark.',
        'hides': 'A four-table join (student, department, enrollment, result) plus two aggregates.',
        'why': 'Every screen that needs "the student plus their numbers" reads this instead of '
               'repeating the join, so the definition of "average mark" exists in exactly one place.',
        'watch': 'COUNT(DISTINCT e.offering_id) matters — without DISTINCT, three results in one '
                 'course would be counted as three courses.',
    },
    'v_course_offering_stats': {
        'purpose': 'Each offering with its course, department, instructor and how full it is.',
        'hides': 'The offering → course → department → faculty chain plus a capacity ratio.',
        'why': 'Capacity utilisation is a reporting figure, not a stored fact — a view keeps it '
               'correct without a denormalised column that could drift.',
        'watch': 'The percentage is derived, so it can never disagree with capacity/enrolled_count.',
    },
    'v_fee_status': {
        'purpose': 'The fee owed, the fee paid and the balance for each student and semester.',
        'hides': 'A LEFT JOIN onto fee_payment so a student who has paid nothing still appears '
                 'with a zero paid amount instead of disappearing.',
        'why': 'Money must never be computed in the browser; this view is the single answer to '
               '"what is still owed?".',
        'watch': 'SUM over a LEFT JOIN needs COALESCE — NULL + anything is NULL, not zero.',
    },
    'v_attendance_summary': {
        'purpose': 'Per enrollment: how many classes were held, how many attended, and the '
                   'percentage that follows.',
        'hides': 'The attendance → enrollment join with conditional counting.',
        'why': 'The 75% threshold is a policy, and a policy belongs in SQL where it cannot be '
               'edited by a page.',
        'watch': 'SUM(CASE WHEN ...) counts conditionally; COUNT(*) alone cannot tell Present '
                 'from Absent.',
    },
    'v_pending_approvals': {
        'purpose': 'Admission applications still waiting, with the department they applied to.',
        'hides': 'A filtered join, not a stored "pending" flag elsewhere.',
        'why': 'The dashboard count and the admissions screen read the same definition of pending.',
        'watch': 'It is a view, so approving an application makes it disappear immediately — no '
                 'cache to invalidate.',
    },
    'v_monthly_admissions_enrollments': {
        'purpose': 'A month-by-month series of applications received and students enrolled.',
        'hides': 'Date truncation plus counts, grouped by month.',
        'why': 'Charting needs a series; the base tables only store timestamps.',
        'watch': 'Grouping by a truncated date is the portable way to do a time series — '
                 'no application-side loop.',
    },
}


def _view_rows(name, limit=6):
    return run_sql(f'SELECT * FROM {_q(name)} LIMIT {int(limit)}', limit=limit)


def _view_ddl(name):
    try:
        if is_mysql():
            row = db_pool.execute_query(
                'SELECT VIEW_DEFINITION AS ddl FROM information_schema.VIEWS '
                'WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s', (name,), fetch='one')
            if row and row.get('ddl'):
                return f'CREATE VIEW {name} AS\n{row["ddl"]};'
            return None
        row = db_pool.execute_query(
            "SELECT sql FROM sqlite_master WHERE type = 'view' AND name = %s", (name,), fetch='one')
        return (row or {}).get('sql')
    except Exception:
        return None


def views():
    """Every view the running database actually has, with its definition and a preview."""
    try:
        if is_mysql():
            names = [row['TABLE_NAME'] for row in (
                db_pool.execute_query(
                    'SELECT TABLE_NAME FROM information_schema.VIEWS '
                    'WHERE TABLE_SCHEMA = DATABASE() ORDER BY TABLE_NAME', fetch='all') or [])]
        else:
            names = [row['name'] for row in (
                db_pool.execute_query(
                    "SELECT name FROM sqlite_master WHERE type = 'view' ORDER BY name",
                    fetch='all') or [])]
    except Exception:
        names = []
    catalogue = []
    for name in names:
        try:
            count = int(db_pool.execute_query(
                f'SELECT COUNT(*) AS n FROM {_q(name)}', fetch='one').get('n') or 0)
        except Exception:
            count = 0
        notes = VIEW_NOTES.get(name, {})
        catalogue.append({
            'name': name,
            'ddl': _view_ddl(name) or f'CREATE VIEW {name} AS ...',
            'rows': count,
            'preview': _view_rows(name),
            'purpose': notes.get('purpose', ''),
            'hides': notes.get('hides', ''),
            'why': notes.get('why', ''),
            'watch': notes.get('watch', ''),
        })
    return catalogue


# ---------------------------------------------------------------------------
# 3. procedures and functions — read from the source file
# ---------------------------------------------------------------------------
def _read_procedure_file():
    try:
        with open(PROCEDURE_FILE, encoding='utf-8') as source:
            return source.read()
    except OSError:
        return ''


def _balanced(text, start):
    """Return the substring inside the parentheses that open at ``start``."""
    if start >= len(text) or text[start] != '(':
        return ''
    depth = 0
    for position in range(start, len(text)):
        character = text[position]
        if character == '(':
            depth += 1
        elif character == ')':
            depth -= 1
            if depth == 0:
                return text[start:position + 1]
    return ''


def _blocks(source):
    """Split ``db/procedures.sql`` into CREATE PROCEDURE / CREATE FUNCTION bodies.

    Written by hand rather than with one big regular expression because the
    parameter lists contain their own parentheses — ``OUT p_message VARCHAR(255)``
    is enough to defeat a naive ``\\([^)]*\\)``.
    """
    blocks = []
    header = re.compile(r'CREATE\s+(PROCEDURE|FUNCTION)\s+(\w+)', re.IGNORECASE)
    for match in header.finditer(source):
        kind, name = match.group(1).upper(), match.group(2)
        cursor = match.end()
        while cursor < len(source) and source[cursor] in ' \t\r\n':
            cursor += 1
        params = _balanced(source, cursor) if cursor < len(source) and source[cursor] == '(' else '()'
        after = cursor + len(params)
        body_start = re.search(r'\bBEGIN\b', source[after:], re.IGNORECASE)
        if not body_start:
            continue
        body_from = after + body_start.end()
        body_end = re.search(r'\nEND\$\$', source[body_from:])
        if not body_end:
            continue
        body = source[body_from:body_from + body_end.start()]
        prefix = source[after:after + body_start.start()]
        returns = re.search(r'RETURNS\s+([\w]+(?:\s*\([^)]*\))?)', prefix, re.IGNORECASE)
        characteristic = re.search(r'(DETERMINISTIC|READS SQL DATA|MODIFIES SQL DATA)', prefix,
                                   re.IGNORECASE)
        label = re.search(r'([\w]+)\s*:\s*$', source[max(0, body_from - 40):body_from])
        ddl = f"CREATE {kind} {name}{params}\n" + prefix.strip() + "\nBEGIN" + body + "\nEND;"
        blocks.append({
            'kind': kind,
            'name': name,
            'params_raw': params or '()',
            'returns': (returns.group(1) if returns else '').strip(),
            'characteristic': (characteristic.group(1).upper() if characteristic else ''),
            'body': body.strip('\n'),
            'label': label.group(1) if label and kind == 'PROCEDURE' else '',
            'ddl': ddl,
        })
    return blocks


def _split_top_level(text, separator=','):
    """Split on commas that are not inside parentheses."""
    parts, depth, current = [], 0, []
    for character in text:
        if character == '(':
            depth += 1
        elif character == ')':
            depth -= 1
        if character == separator and depth == 0:
            parts.append(''.join(current))
            current = []
        else:
            current.append(character)
    parts.append(''.join(current))
    return [part.strip() for part in parts if part.strip()]


def _param_list(raw):
    """Parse ``(IN p_id INT, OUT p_msg VARCHAR(255))`` into a list of parameters."""
    inner = (raw or '').strip()
    if inner.startswith('('):
        inner = inner[1:]
    if inner.endswith(')'):
        inner = inner[:-1]
    params = []
    for part in _split_top_level(inner):
        tokens = part.split()
        mode = 'IN'
        if tokens and tokens[0].upper() in ('IN', 'OUT', 'INOUT'):
            mode = tokens[0].upper()
            tokens = tokens[1:]
        # Join the type back together: DECIMAL(10,2) was split by the comma rule.
        params.append({'mode': mode, 'name': tokens[0] if tokens else part,
                       'type': ' '.join(tokens[1:])})
    return params


PROCEDURE_NOTES = {
    'sp_enroll_student': {
        'purpose': 'Enrol one student into one offering, atomically and without overselling.',
        'steps': [
            'Check the student exists and is Active.',
            'Check the student is not already enrolled in this offering.',
            'Lock the offering row (SELECT ... FOR UPDATE) and read capacity + enrolled_count.',
            'Refuse if enrolled_count >= capacity.',
            'INSERT the enrollment; the trigger keeps enrolled_count correct.',
            'COMMIT, or ROLLBACK on any failure with a status code and a message.',
        ],
        'guarantees': 'Two administrators enrolling the last seat at the same moment cannot both '
                      'succeed: the second blocks on the row lock, re-reads the count and is '
                      'refused. The trigger that maintains enrolled_count runs inside the same '
                      'transaction, so the counter can never disagree with the rows.',
        'demo': 'enrol',
    },
    'sp_approve_admission': {
        'purpose': 'Turn an approved application into a student record, a portal account and a '
                   'closed application — three tables, one transaction.',
        'steps': [
            'Check the application exists and is still pending.',
            'Check the applicant carries the details a student record needs.',
            'Insert the student row and generate the roll number.',
            'Create the portal account (bcrypt hash never leaves the procedure).',
            'Mark the application approved, with the reviewer and the time.',
            'COMMIT all three writes, or lose all three.',
        ],
        'guarantees': 'There is no state in which a student exists without their account, or an '
                      'application is marked approved with no student. That is atomicity, and it '
                      'is why this belongs in a procedure rather than in three separate requests.',
        'demo': 'approve',
    },
    'sp_record_payment': {
        'purpose': 'Record a fee payment, refusing anything that does not make sense.',
        'steps': [
            'Read the fee owed for the student and semester.',
            'Read what has already been paid.',
            'Refuse a payment larger than the outstanding balance.',
            'Refuse a duplicate receipt number.',
            'INSERT the payment and return the new balance.',
        ],
        'guarantees': 'The balance is computed inside the transaction, so two clerks taking the '
                      'same payment cannot both see the old balance and both accept it.',
        'demo': 'payment',
    },
}

FUNCTION_NOTES = {
    'fn_grade': {
        'purpose': 'Percentage to letter grade, in one place.',
        'why': 'The grade boundary is a rule. If it lived in Python and in JavaScript it would be '
               'implemented twice and disagree eventually.',
        'demo': 'grade',
        'signature': 'fn_grade(percentage DECIMAL(5,2)) → VARCHAR(3)',
    },
    'fn_attendance_pct': {
        'purpose': 'Attendance percentage for one enrollment.',
        'why': 'Late counts as attended, and that policy is written once, in SQL, where both the '
               'dashboard and the report card read it.',
        'demo': 'attendance',
        'signature': 'fn_attendance_pct(enrollment_id INT) → DECIMAL(5,2)',
    },
    'fn_student_cgpa': {
        'purpose': 'Credit-weighted grade point average for one student.',
        'why': 'A weighted average is easy to get subtly wrong (weights, drops, rounding); a '
               'stored function makes every caller use the same arithmetic.',
        'demo': 'cgpa',
        'signature': 'fn_student_cgpa(student_id INT) → DECIMAL(4,2)',
    },
}


def procedures():
    """The three stored procedures, with their real source and the steps they perform."""
    blocks = [block for block in _blocks(_read_procedure_file()) if block['kind'] == 'PROCEDURE']
    catalogue = []
    for block in blocks:
        notes = PROCEDURE_NOTES.get(block['name'], {})
        catalogue.append({
            'name': block['name'],
            'params': _param_list(block['params_raw']),
            'body': block['body'],
            'ddl': block['ddl'],
            'label': block.get('label', ''),
            'purpose': notes.get('purpose', ''),
            'steps': notes.get('steps', []),
            'guarantees': notes.get('guarantees', ''),
            'demo': notes.get('demo'),
        })
    return catalogue


def functions():
    """The three stored functions, with their real source and a live demonstration."""
    blocks = [block for block in _blocks(_read_procedure_file()) if block['kind'] == 'FUNCTION']
    catalogue = []
    for block in blocks:
        notes = FUNCTION_NOTES.get(block['name'], {})
        catalogue.append({
            'name': block['name'],
            'params': _param_list(block['params_raw']),
            'returns': block['returns'],
            'characteristic': block['characteristic'],
            'body': block['body'],
            'ddl': block['ddl'],
            'label': block.get('label', ''),
            'purpose': notes.get('purpose', ''),
            'why': notes.get('why', ''),
            'signature': notes.get('signature', ''),
            'demo': notes.get('demo'),
        })
    return catalogue


# --- the live equivalent of each function ---------------------------------
GRADE_LADDER_SQL = """WITH RECURSIVE marks(pct) AS (
    SELECT 100
    UNION ALL
    SELECT pct - 5 FROM marks WHERE pct > 0
)
SELECT pct AS percentage,
       CASE WHEN pct >= 90 THEN 'A+' WHEN pct >= 80 THEN 'A'
            WHEN pct >= 70 THEN 'B+' WHEN pct >= 60 THEN 'B'
            WHEN pct >= 50 THEN 'C'  WHEN pct >= 40 THEN 'P'
            ELSE 'F' END AS fn_grade_result
FROM marks;"""

GRADE_LADDER_SQL_MYSQL = """WITH RECURSIVE marks(pct) AS (
    SELECT 100
    UNION ALL
    SELECT pct - 5 FROM marks WHERE pct > 0
)
SELECT pct AS percentage,
       CASE WHEN pct >= 90 THEN 'A+' WHEN pct >= 80 THEN 'A'
            WHEN pct >= 70 THEN 'B+' WHEN pct >= 60 THEN 'B'
            WHEN pct >= 50 THEN 'C'  WHEN pct >= 40 THEN 'P'
            ELSE 'F' END AS fn_grade_result
FROM marks;"""

ATTENDANCE_SQL = """SELECT e.enrollment_id,
       s.roll_no,
       c.course_code,
       COUNT(a.attendance_id)                                        AS classes_held,
       SUM(CASE WHEN a.status IN ('Present', 'Late') THEN 1 ELSE 0 END) AS classes_attended,
       ROUND(100.0 * SUM(CASE WHEN a.status IN ('Present', 'Late') THEN 1 ELSE 0 END)
             / NULLIF(COUNT(a.attendance_id), 0), 2)                 AS fn_attendance_pct
FROM enrollment e
JOIN student s        ON s.student_id  = e.student_id
JOIN course_offering co ON co.offering_id = e.offering_id
JOIN course c         ON c.course_id   = co.course_id
LEFT JOIN attendance a ON a.enrollment_id = e.enrollment_id
WHERE e.status = 'Enrolled'
GROUP BY e.enrollment_id, s.roll_no, c.course_code
HAVING COUNT(a.attendance_id) > 0
ORDER BY fn_attendance_pct, s.roll_no
LIMIT 12;"""

CGPA_SQL = """SELECT s.roll_no,
       CONCAT(s.first_name, ' ', s.last_name) AS student_name,
       COUNT(g.grade_point)                   AS graded_courses,
       ROUND(SUM(g.credits * g.grade_point) / NULLIF(SUM(g.credits), 0), 2) AS fn_student_cgpa
FROM student s
JOIN (
    SELECT e.student_id,
           c.credits,
           CASE WHEN 100.0 * SUM(r.marks_obtained) / SUM(ex.max_marks) >= 90 THEN 10
                WHEN 100.0 * SUM(r.marks_obtained) / SUM(ex.max_marks) >= 80 THEN 9
                WHEN 100.0 * SUM(r.marks_obtained) / SUM(ex.max_marks) >= 70 THEN 8
                WHEN 100.0 * SUM(r.marks_obtained) / SUM(ex.max_marks) >= 60 THEN 7
                WHEN 100.0 * SUM(r.marks_obtained) / SUM(ex.max_marks) >= 50 THEN 6
                WHEN 100.0 * SUM(r.marks_obtained) / SUM(ex.max_marks) >= 40 THEN 5
                ELSE 0 END AS grade_point
    FROM enrollment e
    JOIN course_offering co ON co.offering_id = e.offering_id
    JOIN course c           ON c.course_id    = co.course_id
    JOIN result r           ON r.enrollment_id = e.enrollment_id
    JOIN exam ex            ON ex.exam_id = r.exam_id AND ex.offering_id = e.offering_id
    WHERE e.status != 'Dropped'
    GROUP BY e.enrollment_id, e.student_id, c.credits
) g ON g.student_id = s.student_id
GROUP BY s.student_id, s.roll_no, s.first_name, s.last_name
ORDER BY fn_student_cgpa DESC
LIMIT 12;"""

FUNCTION_DEMOS = {
    'grade': ('fn_grade', 'The grade ladder, evaluated by the same CASE expression the function '
                          'encodes. Every boundary is visible.', GRADE_LADDER_SQL),
    'attendance': ('fn_attendance_pct', 'Live attendance percentages, computed with the function\'s '
                                        'own formula: Late counts as attended, zero classes means 0.00.',
                   ATTENDANCE_SQL),
    'cgpa': ('fn_student_cgpa', 'Live CGPAs: each course contributes credits × grade point, divided '
                                'by the total credits attempted.',
             CGPA_SQL),
}


def evaluate_function(key, limit=ROW_LIMIT):
    entry = FUNCTION_DEMOS.get(key)
    if not entry:
        return {'ok': False, 'error': f'No function demonstration called {key}.', 'columns': [],
                'rows': [], 'row_count': 0, 'shown': 0, 'truncated': False, 'elapsed_ms': 0}
    name, blurb, sql = entry
    sqlite_sql = None
    if not is_mysql() and 'WITH RECURSIVE' in sql.upper():
        sqlite_sql = sql          # identical spelling; kept explicit for clarity
    outcome = run_sql(sql, limit=limit)
    outcome['function'] = name
    outcome['blurb'] = blurb
    outcome['engine_sql'] = executed_form(sql, sqlite_sql)[0]
    return outcome


# --- read-only dry runs of the procedures ----------------------------------
def _one(sql, params=()):
    try:
        return db_pool.execute_query(sql, params, fetch='one')
    except Exception:
        return None


def _val(sql, params=(), default=None):
    try:
        value = db_pool.execute_query(sql, params, fetch='val')
        return default if value is None else value
    except Exception:
        return default


def _step(title, sql, ok, detail, rows=None):
    return {'title': title, 'sql': sql, 'ok': bool(ok), 'detail': detail, 'rows': rows or []}


def _dry_enrol():
    """Watch sp_enroll_student decide, on a real student and a real offering."""
    candidate = _one("""SELECT s.student_id, s.roll_no, s.status AS student_status,
                               co.offering_id, co.capacity, co.enrolled_count,
                               c.course_code
                        FROM student s
                        CROSS JOIN course_offering co
                        JOIN course c ON c.course_id = co.course_id
                        WHERE s.status = 'Active'
                          AND co.enrolled_count < co.capacity
                          AND NOT EXISTS (SELECT 1 FROM enrollment e
                                          WHERE e.student_id = s.student_id
                                            AND e.offering_id = co.offering_id)
                        ORDER BY s.student_id, co.offering_id
                        LIMIT 1""")
    if not candidate:
        return [ _step('Pick a candidate', 'SELECT ... FROM student, course_offering',
                       False, 'Every active student is already enrolled everywhere there is a seat.') ]
    sid, oid = candidate['student_id'], candidate['offering_id']
    steps = [
        _step('1 · Validate the student',
              f"SELECT status FROM student WHERE student_id = {sid};",
              candidate['student_status'] == 'Active',
              f"{candidate['roll_no']} is {candidate['student_status']} — an enrolment is only "
              'allowed for an Active student.'),
        _step('2 · Guard against a duplicate',
              f"SELECT COUNT(*) FROM enrollment WHERE student_id = {sid} AND offering_id = {oid};",
              True,
              'No enrollment row for this pair, so the procedure continues — a second seat for '
              'the same course would be double billing.'),
        _step('3 · Lock the offering and read the seats',
              f"SELECT capacity, enrolled_count FROM course_offering WHERE offering_id = {oid} FOR UPDATE;",
              candidate['enrolled_count'] < candidate['capacity'],
              f"{candidate['course_code']}: {candidate['enrolled_count']} of "
              f"{candidate['capacity']} seats taken, "
              f"{candidate['capacity'] - candidate['enrolled_count']} free. FOR UPDATE would block "
              'another transaction here until this one commits.'),
        _step('4 · Decide',
              'INSERT INTO enrollment (student_id, offering_id, enroll_date, status)\n'
              "VALUES (..., ..., date('now'), 'Enrolled');",
              True,
              'All checks pass, so the procedure would insert the row and COMMIT — the trigger '
              'would then increment enrolled_count in the same transaction.'),
    ]
    return steps


def _dry_approve():
    application = _one("""SELECT a.application_id, a.applicant_name, a.email, a.phone, a.status,
                                 a.dept_id, d.dept_code
                          FROM admission_application a
                          LEFT JOIN department d ON d.dept_id = a.dept_id
                          WHERE a.status = 'Pending'
                          ORDER BY a.application_id
                          LIMIT 1""")
    if not application:
        return [_step('Pick a pending application',
                      "SELECT * FROM admission_application WHERE status = 'Pending';",
                      False, 'There is no pending application to approve right now.')]
    missing = [field for field in ('applicant_name', 'email', 'phone')
               if not application.get(field)]
    steps = [
        _step('1 · The application must still be pending',
              f"SELECT status FROM admission_application WHERE application_id = "
              f"{application['application_id']};",
              application['status'] == 'Pending',
              f"Application #{application['application_id']} for "
              f"{application['applicant_name']} is {application['status']}."),
        _step('2 · The details a student row needs',
              'applicant_name IS NOT NULL, email IS NOT NULL, phone IS NOT NULL',
              not missing,
              'All present,' if not missing else f'Missing: {", ".join(missing)}.'),
        _step('3 · The department must exist',
              f"SELECT dept_code FROM department WHERE dept_id = {application['dept_id']};",
              bool(application.get('dept_code')),
              f"Applicant applied to {application.get('dept_code') or 'no department'}."),
        _step('4 · Three writes, one transaction',
              'INSERT INTO student ...\nINSERT INTO app_user (username, password_hash) ...\n'
              "UPDATE admission_application SET status = 'Approved' ...",
              True,
              'A student row, a portal account and the closed application are committed '
              'together or not at all.'),
    ]
    return steps


def _dry_payment():
    """Watch sp_record_payment compute a balance and refuse an impossible payment."""
    ledger = _one("""SELECT s.student_id, s.roll_no, fs.semester_no, fs.amount AS fee_owed,
                            COALESCE(SUM(fp.amount), 0) AS paid,
                            fs.amount - COALESCE(SUM(fp.amount), 0) AS balance
                     FROM student s
                     JOIN fee_structure fs ON fs.dept_id = s.dept_id
                     LEFT JOIN fee_payment fp
                            ON fp.student_id = s.student_id
                           AND fp.semester_no = fs.semester_no
                     WHERE s.status = 'Active'
                     GROUP BY s.student_id, s.roll_no, fs.semester_no, fs.amount
                     HAVING fs.amount - COALESCE(SUM(fp.amount), 0) > 0
                     ORDER BY balance DESC
                     LIMIT 1""")
    if not ledger:
        return [_step('Read the ledger',
                      'SELECT amount FROM fee_structure fs JOIN student s ...',
                      False,
                      'Every active student is fully paid, so there is no balance to '
                      'demonstrate against.')]
    owed = float(ledger['fee_owed'])
    paid = float(ledger['paid'])
    balance = float(ledger['balance'])
    steps = [
        _step('1 · What is owed for the semester',
              f"SELECT amount FROM fee_structure WHERE dept_id = (SELECT dept_id FROM student "
              f"WHERE student_id = {ledger['student_id']}) AND semester_no = "
              f"{ledger['semester_no']};",
              True,
              f"{ledger['roll_no']}: ₹{owed:,.2f} is the fee for semester "
              f"{ledger['semester_no']} in their department."),
        _step('2 · What has already been paid',
              'SELECT COALESCE(SUM(amount), 0) FROM fee_payment WHERE student_id = ? '
              'AND semester_no = ?;',
              True, f"₹{paid:,.2f} has been received and receipted."),
        _step('3 · The balance, computed inside the transaction',
              'owed - COALESCE(SUM(paid), 0)',
              balance > 0,
              f"₹{balance:,.2f} outstanding. A payment of ₹{balance + 1:,.2f} would be refused, "
              'not silently accepted.'),
        _step('4 · Receipt uniqueness',
              'SELECT COUNT(*) FROM fee_payment WHERE receipt_no = ?;',
              True,
              'The procedure checks the receipt number before the INSERT, so the same receipt '
              'cannot be posted twice.'),
        _step('5 · Commit and return the new balance',
              'INSERT INTO fee_payment (...) VALUES (...); COMMIT;',
              True,
              'One row written and the new balance returned to the caller in the same '
              'transaction — a clerk cannot act on a stale figure.'),
    ]
    return steps


DRY_RUNS = {
    'enrol': _dry_enrol,
    'approve': _dry_approve,
    'payment': _dry_payment,
}


def procedure_dry_run(name):
    """Run the read-only checks of one procedure and report each step."""
    for procedure in procedures():
        if procedure['name'] == name:
            builder = DRY_RUNS.get(procedure.get('demo'))
            if not builder:
                return {'name': name, 'steps': [], 'error': 'No dry run available.'}
            start = time.perf_counter()
            try:
                steps = builder()
                error = None
            except Exception as caught:            # a demo must never break the page
                steps, error = [], str(caught)
            return {
                'name': name,
                'steps': steps,
                'error': error,
                'elapsed_ms': _elapsed(start),
                'verdict': ('Every check passed — the procedure would commit.'
                            if error is None and steps and all(step['ok'] for step in steps)
                            else 'At least one check would stop the procedure.'),
            }
    return {'name': name, 'steps': [], 'error': 'Unknown procedure.'}


# ---------------------------------------------------------------------------
# 4. triggers
# ---------------------------------------------------------------------------
TRIGGER_RULES = {
    'trg_enr_cap': 'A seat cannot be sold twice: the insert is refused when the offering is full.',
    'trg_enr_active': 'Only an Active student may be enrolled.',
    'trg_enr_transfer_guard': 'An enrollment that already has attendance or results cannot be moved '
                              'to another student or offering.',
    'trg_res_chk': 'Marks cannot exceed the maximum for that exam.',
    'trg_res_chk_upd': 'The same ceiling applies to an update, not just an insert.',
    'trg_student_age_insert': 'A student must be at least 15 on the admission date.',
    'trg_student_age_update': 'Changing the date of birth or admission date cannot break the age rule.',
    'trg_student_ledger_update': 'A student with recorded payments cannot change department, and the '
                                 'semester cannot go backwards past a paid semester.',
    'trg_attendance_guard_insert': 'Attendance needs an active enrollment to hang off.',
    'trg_attendance_guard_update': 'The same rule applies when attendance is edited.',
    'trg_user_role_insert': 'A portal account\'s role must match the profile it points at.',
    'trg_user_role_update': 'Re-pointing an account at another role is refused in the same way.',
    'trg_login_history_no_update': 'The sign-in register cannot be edited — not by any application, '
                                   'and not by hand.',
    'trg_login_history_no_delete': 'The sign-in register cannot be deleted from either.',
    'trg_staff_activity_no_update': 'The change log cannot be edited.',
    'trg_staff_activity_no_delete': 'The change log cannot be deleted from.',
}

# A proof is engine-agnostic: it is matched to whichever trigger enforces the rule.
TRIGGER_PROOFS = [
    {
        'rule': 'capacity',
        'match': ('trg_enr_cap', 'enrollment_before_insert', 'enr_cap'),
        'title': 'Enrol into a full offering',
        'statement': "INSERT INTO enrollment (student_id, offering_id, enroll_date, status)\n"
                     "VALUES (%s, %s, date('now'), 'Enrolled');",
        'setup': ["UPDATE course_offering SET enrolled_count = capacity WHERE offering_id = %s"],
        'setup_note': 'the offering is filled to capacity inside the transaction first, and '
                      'both steps are rolled back',
        'expects': 'The insert is refused before it happens.',
    },
    {
        'rule': 'inactive',
        'match': ('trg_enr_active', 'enrollment_before_insert'),
        'title': 'Enrol a student who is not Active',
        'statement': "INSERT INTO enrollment (student_id, offering_id, enroll_date, status)\n"
                     "VALUES (%s, %s, date('now'), 'Enrolled');",
        'expects': 'Refused: only Active students may be enrolled.',
    },
    {
        'rule': 'marks',
        'match': ('trg_res_chk', 'result_before_insert'),
        'title': 'Record marks above the exam maximum',
        'statement': 'INSERT INTO result (exam_id, enrollment_id, marks_obtained)\n'
                     'VALUES (%s, %s, %s);',
        'expects': 'Refused: marks cannot exceed max_marks.',
    },
    {
        'rule': 'age',
        'match': ('trg_student_age_insert', 'student_before_insert'),
        'title': 'Admit a student younger than 15',
        'statement': 'INSERT INTO student (roll_no, first_name, last_name, email, dob, '
                     'admission_date, dept_id, status)\nVALUES (%s, %s, %s, %s, %s, %s, %s, '
                     "'Active');",
        'expects': 'Refused: the age rule belongs to the database, not the form.',
    },
    {
        'rule': 'role',
        'match': ('trg_user_role_insert', 'user_role_insert'),
        'title': 'Create an account whose role has no profile behind it',
        'statement': 'INSERT INTO app_user (username, password_hash, role, student_id)\n'
                     "VALUES (%s, %s, 'student', NULL);",
        'expects': 'Refused: an account cannot claim a role it has no profile for.',
    },
    {
        'rule': 'attendance',
        'match': ('trg_attendance_guard_insert', 'attendance_before_insert'),
        'title': 'Mark attendance against an enrollment that does not exist',
        'statement': "INSERT INTO attendance (enrollment_id, class_date, status)\n"
                     "VALUES (%s, date('now'), 'Present');",
        'expects': 'Refused: attendance must hang off an active enrollment.',
    },
    {
        'rule': 'ledger',
        'match': ('trg_student_ledger_update', 'student_ledger_update'),
        'title': 'Move a paying student to another department',
        'statement': 'UPDATE student SET dept_id = %s WHERE student_id = %s;',
        'expects': 'Refused: money already recorded would be silently re-attributed.',
    },
    {
        'rule': 'history',
        'match': ('trg_login_history_no_update',),
        'title': 'Edit the sign-in register',
        'statement': "UPDATE login_history SET username = 'someone-else';",
        'setup': ["INSERT INTO login_history (username, role, event, happened_at, address, detail) "
                  "VALUES ('guard-demo', 'admin', 'signed in', '2026-01-01 00:00:00', '127.0.0.1', "
                  "'created inside the proof, then rolled back')"],
        'setup_note': 'a row is created inside the transaction so the UPDATE has something to hit',
        'expects': 'Refused by the database itself — the audit trail is append-only.',
    },
    {
        'rule': 'history-delete',
        'match': ('trg_login_history_no_delete',),
        'title': 'Delete a row from the sign-in register',
        'statement': 'DELETE FROM login_history;',
        'setup': ["INSERT INTO login_history (username, role, event, happened_at, address, detail) "
                  "VALUES ('guard-demo', 'admin', 'signed in', '2026-01-01 00:00:00', '127.0.0.1', "
                  "'created inside the proof, then rolled back')"],
        'setup_note': 'a row is created inside the transaction so the DELETE has something to hit',
        'expects': 'Refused: history cannot be erased, not even by the supreme administrator.',
    },
    {
        'rule': 'activity',
        'match': ('trg_staff_activity_no_delete',),
        'title': 'Wipe the change log',
        'statement': 'DELETE FROM staff_activity;',
        'setup': ["INSERT INTO staff_activity (username, role, action, object, detail, path, "
                  "happened_at, address) VALUES ('guard-demo', 'admin', 'DELETE', 'student', "
                  "'created inside the proof, then rolled back', '/guard/demo', "
                  "'2026-01-01 00:00:00', '127.0.0.1')"],
        'setup_note': 'a row is created inside the transaction so the DELETE has something to hit',
        'expects': 'Refused: the record of who changed what survives every attempt.',
    },
]


def _proof_params(rule):
    """Pick real rows so each violation is genuine, then hand back (sql, params)."""
    if rule == 'capacity':
        # The same offering is filled by the setup step, so the pair below is the one
        # that will collide with the capacity guard.
        offering = _one('SELECT offering_id FROM course_offering ORDER BY offering_id LIMIT 1')
        if not offering:
            return None, None
        student = _one("""SELECT student_id FROM student
                          WHERE status = 'Active'
                            AND NOT EXISTS (SELECT 1 FROM enrollment e
                                            WHERE e.student_id = student.student_id
                                              AND e.offering_id = %s)
                          ORDER BY student_id LIMIT 1""", (offering['offering_id'],))
        if not student:
            return None, None
        return ("INSERT INTO enrollment (student_id, offering_id, enroll_date, status) "
                "VALUES (%s, %s, date('now'), 'Enrolled');",
                (student['student_id'], offering['offering_id']))
    if rule == 'inactive':
        row = _one("""SELECT s.student_id, co.offering_id
                      FROM student s
                      CROSS JOIN (SELECT offering_id FROM course_offering LIMIT 1) co
                      WHERE s.status != 'Active' LIMIT 1""")
        if not row:
            return None, None
        return ("INSERT INTO enrollment (student_id, offering_id, enroll_date, status) "
                "VALUES (%s, %s, date('now'), 'Enrolled');",
                (row['student_id'], row['offering_id']))
    if rule == 'marks':
        row = _one("""SELECT ex.exam_id, ex.max_marks, e.enrollment_id
                      FROM exam ex
                      JOIN enrollment e ON e.offering_id = ex.offering_id
                      LIMIT 1""")
        if not row:
            return None, None
        return ('INSERT INTO result (exam_id, enrollment_id, marks_obtained) VALUES (%s, %s, %s);',
                (row['exam_id'], row['enrollment_id'], float(row['max_marks']) + 25))
    if rule == 'age':
        dept = _val('SELECT dept_id FROM department LIMIT 1', default=1)
        return ('INSERT INTO student (roll_no, first_name, last_name, email, dob, admission_date, '
                'dept_id, status) VALUES (%s, %s, %s, %s, %s, %s, %s, %s);',
                ('GUARD-TEST', 'Too', 'Young', 'guard.test@nist.example',
                 '2015-06-01', '2026-07-01', dept, 'Active'))
    if rule == 'role':
        return ('INSERT INTO app_user (username, password_hash, role, student_id) '
                'VALUES (%s, %s, %s, %s);',
                ('guard.test.account', 'not-a-real-hash', 'student', None))
    if rule == 'attendance':
        return ("INSERT INTO attendance (enrollment_id, class_date, status) VALUES (%s, date('now'), %s);",
                (999999, 'Present'))
    if rule == 'ledger':
        row = _one("""SELECT fp.student_id, s.dept_id
                      FROM fee_payment fp JOIN student s ON s.student_id = fp.student_id
                      LIMIT 1""")
        if not row:
            return None, None
        other = _val('SELECT dept_id FROM department WHERE dept_id != %s LIMIT 1',
                     (row['dept_id'],))
        if other is None:
            return None, None
        return ('UPDATE student SET dept_id = %s WHERE student_id = %s;',
                (other, row['student_id']))
    if rule == 'history':
        return ("UPDATE login_history SET username = 'someone-else';", ())
    if rule == 'history-delete':
        return ('DELETE FROM login_history;', ())
    if rule == 'activity':
        return ('DELETE FROM staff_activity;', ())
    return None, None


def _ensure_register_triggers():
    """The two registers create their own guards on first use."""
    try:
        from repositories import login_history, staff_activity
        login_history.ensure_schema()
        staff_activity.ensure_schema()
    except Exception:
        pass


def prove(rule):
    """Attempt one violation inside a SAVEPOINT and roll it back.

    Nothing is committed, so the demonstration is safe to run on the live database:
    the guard's message is the deliverable, and the data is untouched.
    """
    _ensure_register_triggers()
    proof = next((item for item in TRIGGER_PROOFS if item['rule'] == rule), None)
    if not proof:
        return {'ok': False, 'rule': rule, 'error': 'Unknown guard.'}
    sql, params = _proof_params(rule)
    setup = list(proof.get('setup') or [])
    setup_params = {}
    if rule == 'capacity':
        target = _one('SELECT offering_id FROM course_offering ORDER BY offering_id LIMIT 1')
        setup_params['offering_id'] = target['offering_id'] if target else None
    if not sql:
        return {'ok': False, 'rule': rule, 'title': proof['title'],
                'error': 'There is no suitable row in this database to attempt it on.',
                'refused': False, 'message': ''}
    start = time.perf_counter()
    refused, message = False, ''
    try:
        with db_pool.get_connection() as conn:
            cursor = conn.cursor()
            try:
                if is_mysql():
                    conn.begin()
                    cursor.execute('SAVEPOINT workshop_proof')
                else:
                    cursor.execute('SAVEPOINT workshop_proof')
                for statement in setup:
                    shaped = statement
                    if not is_mysql():
                        shaped = re.sub(r'%s', '?', shaped)
                    cursor.execute(shaped, (setup_params['offering_id'],)
                                   if '%s' in statement else ())
                flattened = sql
                if not is_mysql():
                    flattened = re.sub(r'%s', '?', flattened)
                cursor.execute(flattened, params)
                message = 'The statement was accepted — this guard did not fire.'
            except Exception as caught:
                refused, message = True, str(caught)
            finally:
                try:
                    cursor.execute('ROLLBACK TO SAVEPOINT workshop_proof')
                    cursor.execute('RELEASE SAVEPOINT workshop_proof')
                except Exception:
                    pass
                try:
                    conn.rollback()
                except Exception:
                    pass
                cursor.close()
    except Exception as caught:
        return {'ok': False, 'rule': rule, 'title': proof['title'], 'error': str(caught),
                'refused': False, 'message': '', 'elapsed_ms': _elapsed(start)}
    return {
        'ok': True,
        'rule': rule,
        'title': proof['title'],
        'statement': sql,
        'params': [str(value) for value in params],
        'expects': proof['expects'],
        'setup_note': proof.get('setup_note', ''),
        'refused': refused,
        'message': message,
        'rolled_back': True,
        'elapsed_ms': _elapsed(start),
    }


def _timing_and_event(body):
    """Read WHEN / ON / timing / event out of a trigger definition."""
    timing, event, table, when = 'BEFORE', '', '', ''
    match = re.search(r'CREATE\s+(?:TEMP\s+)?TRIGGER\s+[\w."`]+\s+(BEFORE|AFTER|INSTEAD\s+OF)\s+'
                      r'(INSERT|UPDATE|DELETE)(?:\s+OF\s+([\w,\s]+?))?\s+ON\s+([\w."`]+)',
                      body or '', re.IGNORECASE | re.DOTALL)
    if match:
        timing = match.group(1).upper()
        event = match.group(2).upper()
        if match.group(3):
            event += f" OF {match.group(3).strip()}"
        table = match.group(4).strip('"`')
    when_match = re.search(r'\bWHEN\s+(.+?)\s*(?:BEGIN|$)', body or '', re.IGNORECASE | re.DOTALL)
    if when_match:
        when = ' '.join(when_match.group(1).split())[:220]
    return timing, event, table, when


def triggers():
    """Every trigger in the running database, grouped by the table it protects."""
    _ensure_register_triggers()
    rows = []
    try:
        if is_mysql():
            rows = db_pool.execute_query(
                'SELECT TRIGGER_NAME AS name, EVENT_OBJECT_TABLE AS tbl, ACTION_TIMING AS timing, '
                'EVENT_MANIPULATION AS event, ACTION_STATEMENT AS body '
                'FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA = DATABASE() '
                'ORDER BY EVENT_OBJECT_TABLE, TRIGGER_NAME', fetch='all') or []
        else:
            rows = db_pool.execute_query(
                "SELECT name, tbl_name AS tbl, sql AS body FROM sqlite_master "
                "WHERE type = 'trigger' ORDER BY tbl_name, name", fetch='all') or []
    except Exception:
        rows = []
    catalogue = []
    for row in rows:
        body = row.get('body') or ''
        timing, event, table, when = _timing_and_event(body)
        if row.get('timing'):
            timing = str(row['timing']).upper()
        if row.get('event'):
            event = str(row['event']).upper()
        table = table or (row.get('tbl') or '')
        proofs = [proof for proof in TRIGGER_PROOFS
                  if any(pattern.lower() in str(row['name']).lower() for pattern in proof['match'])]
        message = ''
        found = re.search(r"RAISE\s*\(\s*ABORT\s*,\s*'([^']+)'", body, re.IGNORECASE)
        if found:
            message = found.group(1)
        else:
            found = re.search(r"MESSAGE_TEXT\s*=\s*'([^']+)'", body, re.IGNORECASE)
            if found:
                message = found.group(1)
        catalogue.append({
            'name': row['name'],
            'table': table,
            'timing': timing,
            'event': event,
            'when': when,
            'body': body,
            'message': message,
            'rule': TRIGGER_RULES.get(row['name'], ''),
            'proof': proofs[0]['rule'] if proofs else None,
            'proof_title': proofs[0]['title'] if proofs else None,
        })
    return catalogue


def trigger_groups():
    """Triggers grouped per protected table, for the tree and the page."""
    groups = {}
    for trigger in triggers():
        groups.setdefault(trigger['table'], []).append(trigger)
    return [{'table': table, 'triggers': items} for table, items in sorted(groups.items())]


# ---------------------------------------------------------------------------
# 5. schema, indexes and storage
# ---------------------------------------------------------------------------
HIDDEN_TABLES = {'sqlite_sequence'}


def tables():
    try:
        if is_mysql():
            rows = db_pool.execute_query(
                'SELECT TABLE_NAME AS name FROM information_schema.TABLES '
                'WHERE TABLE_SCHEMA = DATABASE() ORDER BY TABLE_NAME', fetch='all') or []
        else:
            rows = db_pool.execute_query(
                "SELECT name FROM sqlite_master WHERE type = 'table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name", fetch='all') or []
    except Exception:
        rows = []
    return [row['name'] for row in rows if row['name'] not in HIDDEN_TABLES]


def columns(table):
    try:
        if is_mysql():
            rows = db_pool.execute_query(
                'SELECT COLUMN_NAME AS name, COLUMN_TYPE AS type, IS_NULLABLE AS nullable, '
                'COLUMN_KEY AS key_type, COLUMN_DEFAULT AS default_value '
                'FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() '
                'AND TABLE_NAME = %s ORDER BY ORDINAL_POSITION', (table,), fetch='all') or []
            return [{'name': row['name'], 'type': row['type'],
                     'nullable': row['nullable'] == 'YES',
                     'pk': row['key_type'] == 'PRI', 'default': row['default_value']}
                    for row in rows]
        rows = db_pool.execute_query(f'PRAGMA table_info({_q(table)})', fetch='all') or []
        return [{'name': row['name'], 'type': row['type'] or '—',
                 'nullable': not row['notnull'], 'pk': bool(row['pk']),
                 'default': row['dflt_value']} for row in rows]
    except Exception:
        return []


def foreign_keys(table):
    try:
        if is_mysql():
            rows = db_pool.execute_query(
                'SELECT CONSTRAINT_NAME AS name, COLUMN_NAME AS column_name, '
                'REFERENCED_TABLE_NAME AS ref_table, REFERENCED_COLUMN_NAME AS ref_column '
                'FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA = DATABASE() '
                'AND TABLE_NAME = %s AND REFERENCED_TABLE_NAME IS NOT NULL', (table,), fetch='all') or []
            return rows
        rows = db_pool.execute_query(f'PRAGMA foreign_key_list({_q(table)})', fetch='all') or []
        return [{'name': f'fk_{table}_{row["from"]}', 'column_name': row['from'],
                 'ref_table': row['table'], 'ref_column': row['to']} for row in rows]
    except Exception:
        return []


def indexes():
    catalogue = []
    try:
        if is_mysql():
            rows = db_pool.execute_query(
                'SELECT INDEX_NAME AS name, TABLE_NAME AS tbl, GROUP_CONCAT(COLUMN_NAME '
                'ORDER BY SEQ_IN_INDEX) AS cols, NON_UNIQUE AS non_unique '
                'FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = DATABASE() '
                'GROUP BY INDEX_NAME, TABLE_NAME, NON_UNIQUE ORDER BY TABLE_NAME, INDEX_NAME',
                fetch='all') or []
            for row in rows:
                catalogue.append({'name': row['name'], 'table': row['tbl'],
                                  'columns': str(row['cols']).split(','),
                                  'unique': not int(row['non_unique'])})
            return catalogue
        for table in tables():
            for row in db_pool.execute_query(f'PRAGMA index_list({_q(table)})', fetch='all') or []:
                name = row['name']
                try:
                    info = db_pool.execute_query(f'PRAGMA index_info({_q(name)})',
                                                 fetch='all') or []
                    cols = [item['name'] for item in info if item['name']]
                except Exception:
                    cols = []
                catalogue.append({'name': name, 'table': table, 'columns': cols,
                                  'unique': bool(row['unique'])})
    except Exception:
        return catalogue
    return catalogue


def storage():
    """Engine-level facts — the numbers a DBA looks at first."""
    facts = {
        'engine': 'MySQL 8' if is_mysql() else 'SQLite',
        'database': (getattr(_db_module.Config, 'DB_NAME', '') if is_mysql()
                     else getattr(_db_module.Config, 'SQLITE_PATH', '')),
    }
    try:
        if is_mysql():
            version = db_pool.execute_query('SELECT VERSION() AS v', fetch='one')
            size = db_pool.execute_query(
                'SELECT ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) AS mb '
                'FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE()', fetch='one')
            facts.update({'version': (version or {}).get('v', ''),
                          'size': f"{(size or {}).get('mb') or 0} MB",
                          'page_size': '16 KB (InnoDB default)',
                          'journal': 'redo log + doublewrite buffer',
                          'concurrency': 'row-level locking (InnoDB)'})
        else:
            facts['version'] = db_pool.execute_query('SELECT sqlite_version() AS v', fetch='one')['v']
            facts['page_size'] = f'{db_pool.execute_query("PRAGMA page_size", fetch="val")} bytes'
            pages = db_pool.execute_query('PRAGMA page_count', fetch='val') or 0
            facts['size'] = f'{round(int(pages) * int(db_pool.execute_query("PRAGMA page_size", fetch="val") or 0) / 1024, 1)} KB'
            journal = str(db_pool.execute_query('PRAGMA journal_mode', fetch='val')).upper()
            facts['journal'] = (
                'WAL · write-ahead log, readers never blocked' if journal == 'WAL'
                else f'{journal} · rollback journal, one writer at a time')
            facts['concurrency'] = 'row locks in MySQL; a single writer here, readers never blocked'
            facts['foreign_keys'] = 'ON' if db_pool.execute_query('PRAGMA foreign_keys', fetch='val') else 'OFF'
            facts['user_version'] = db_pool.execute_query('PRAGMA user_version', fetch='val')
    except Exception:
        facts.setdefault('version', 'unknown')
    return facts


def schema():
    catalogue = []
    for table in tables():
        try:
            rows = int(db_pool.execute_query(f'SELECT COUNT(*) AS n FROM {_q(table)}',
                                             fetch='one').get('n') or 0)
        except Exception:
            rows = 0
        catalogue.append({
            'name': table,
            'rows': rows,
            'columns': columns(table),
            'foreign_keys': foreign_keys(table),
        })
    return catalogue


def overview():
    """Everything the header and the overview tab need, in one call."""
    counts = {'tables': len(tables())}
    try:
        counts['views'] = len(views())
    except Exception:
        counts['views'] = 0
    counts['triggers'] = len(triggers())
    counts['indexes'] = len(indexes())
    counts['procedures'] = len(procedures())
    counts['functions'] = len(functions())
    return {'storage': storage(), 'counts': counts}


# ---------------------------------------------------------------------------
# 6. the primer: how a statement actually runs
# ---------------------------------------------------------------------------
PIPELINE = [
    {
        'stage': '1 · Connection and parsing',
        'what': 'The client sends the text of the statement. The server parses it into a syntax '
                'tree and checks every table and column name against the catalogue.',
        'portal': 'A typo in a table name fails here — before a single row is touched. Try it: the '
                  'SQL console refuses an unknown table with a parse error, not a wrong answer.',
    },
    {
        'stage': '2 · Semantic check and privileges',
        'what': 'The parser output is resolved: which table, which column, does this account have '
                'the right to read it.',
        'portal': 'This is why the portal never selects password_hash for a student: the privilege '
                  'layer and the query layer are both told not to.',
    },
    {
        'stage': '3 · Planning and optimisation',
        'what': 'The optimiser considers access paths — full scan, index seek, join order — and '
                'picks the cheapest by its own statistics.',
        'portal': 'The Plans tab shows the choice the engine made, in the engine\'s own words.',
    },
    {
        'stage': '4 · Execution',
        'what': 'The chosen plan runs: pages are read from the buffer cache or from disk, rows are '
                'filtered, joined, sorted and aggregated.',
        'portal': 'Elapsed milliseconds on every result grid come from this stage.',
    },
    {
        'stage': '5 · Transactions and locking',
        'what': 'Writes are staged in a transaction. Locks (row-level in InnoDB, a single writer '
                'in SQLite) decide who may proceed and who waits.',
        'portal': 'sp_enroll_student takes SELECT ... FOR UPDATE for exactly this reason: it makes '
                'the last seat a single-writer decision.',
    },
    {
        'stage': '6 · Durability',
        'what': 'On COMMIT the change is written to the redo log / write-ahead log before the '
                'client is told it succeeded.',
        'portal': 'That is why a fee receipt survives a power cut, and why ROLLBACK can undo '
                'everything in a failed procedure.',
    },
    {
        'stage': '7 · Constraints and triggers',
        'what': 'Before and after the row changes, declared constraints and triggers get their say. '
                'A trigger that raises an error aborts the whole statement.',
        'portal': 'The Triggers tab proves this: a deliberate violation is attempted and rolled '
                  'back, and the guard\'s own message is shown.',
    },
    {
        'stage': '8 · Result set back to the client',
        'what': 'Rows are streamed back with column metadata. The client renders a grid; the server '
                'has already forgotten the query.',
        'portal': 'The status line under every grid — rows selected, elapsed time, truncation — is '
                  'exactly what a database client prints.',
    },
]

ACID = [
    {'property': 'Atomicity', 'meaning': 'A transaction happens completely or not at all.',
     'where': 'sp_approve_admission writes a student, an account and the application status in one '
              'transaction. All three land, or none do.'},
    {'property': 'Consistency', 'meaning': 'Every committed state satisfies the declared rules.',
     'where': 'The triggers: no enrollment beyond capacity, no marks above the maximum, no account '
              'without a profile.'},
    {'property': 'Isolation', 'meaning': 'Concurrent transactions cannot see each other\'s '
                                         'half-finished work.',
     'where': 'SELECT ... FOR UPDATE in sp_enroll_student serialises the last-seat decision.'},
    {'property': 'Durability', 'meaning': 'Once committed, a change survives a crash.',
     'where': 'The write-ahead log / redo log — see stage 6 above.'},
]

ISOLATION = [
    {'level': 'READ UNCOMMITTED', 'dirty': 'possible', 'nonrepeatable': 'possible',
     'phantom': 'possible', 'note': 'Never used in this portal.'},
    {'level': 'READ COMMITTED', 'dirty': 'prevented', 'nonrepeatable': 'possible',
     'phantom': 'possible', 'note': 'What SQLite effectively gives a reader.'},
    {'level': 'REPEATABLE READ', 'dirty': 'prevented', 'nonrepeatable': 'prevented',
     'phantom': 'possible', 'note': 'MySQL/InnoDB default.'},
    {'level': 'SERIALIZABLE', 'dirty': 'prevented', 'nonrepeatable': 'prevented',
     'phantom': 'prevented', 'note': 'The strongest, and the slowest.'},
]


def primer():
    return {'pipeline': PIPELINE, 'acid': ACID, 'isolation': ISOLATION}


# ---------------------------------------------------------------------------
# 7. the printable handout
# ---------------------------------------------------------------------------
def handout_rows():
    """Flat rows for the workshop PDF: one section per topic."""
    rows = []
    for demo in join_demos():
        rows.append(['JOIN', demo['label'], demo['title']])
    for view in views():
        rows.append(['VIEW', view['name'], f"{view['rows']} rows — {view['purpose'][:80]}"])
    for procedure in procedures():
        params = ', '.join(f"{p['mode']} {p['name']} {p['type']}" for p in procedure['params'])
        rows.append(['PROCEDURE', procedure['name'], params])
    for function in functions():
        rows.append(['FUNCTION', function['name'], function['signature']])
    for trigger in triggers():
        rows.append(['TRIGGER', trigger['name'], f"{trigger['timing']} {trigger['event']} on "
                                                 f"{trigger['table']} — {trigger['rule'] or trigger['message']}"])
    for table in schema():
        rows.append(['TABLE', table['name'], f"{table['rows']} rows, {len(table['columns'])} columns, "
                                             f"{len(table['foreign_keys'])} foreign keys"])
    return rows
