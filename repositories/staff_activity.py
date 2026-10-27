"""Append-only record of what administrators and faculty changed.

Nobody has to remember to call this. Every successful state-changing request an
administrator or a faculty member makes is captured in one central place — the
student form, a fee receipt, a bulk attendance save, the SQL console, a
password reset — so the list answers three questions on its own: **who**
(username and role), **what** (the change, the table and the fields that were
sent) and **when** (UTC on disk, the portal's timezone on screen).

Like the sign-in history the table is append-only:

* no UPDATE/DELETE path in the application,
* SQLite/MySQL triggers abort any UPDATE or DELETE,
* the SQL console refuses to write to it,
* the raw-data viewer only reads it.

Students are never recorded here: the request says the register is for
administrators and faculty, so those are the only two roles written.
"""
import re
from datetime import datetime, timedelta, timezone

from repositories.db_pool import db_pool

TABLE = 'staff_activity'
ROLES = ('admin', 'faculty')
WRITE_METHODS = ('POST', 'PUT', 'PATCH', 'DELETE')
LOCKED_TABLES = {
    'login_history', 'staff_activity', 'admin_session', 'owner_guard',
    'admin_access_request', 'audit_log',
}
# Pages that are not a change to campus data: they have their own registers.
SKIP_ENDPOINTS = {
    'auth.login_api', 'auth.logout', 'auth.access_status', 'auth.login_view',
    'auth.reset_password_api', 'static',
}
# Screen names mapped to the table they write.
OBJECT_BY_PATH = {
    'students': 'student',
    'faculty': 'faculty',
    'departments': 'department',
    'courses': 'course',
    'offerings': 'course_offering',
    'enrollments': 'enrollment',
    'attendance': 'attendance',
    'results': 'result',
    'exams': 'exam',
    'fees': 'fee_payment',
    'admissions': 'admission_application',
    'insights': 'database',
    'owner': 'admin_guard',
}
SECRET_HINTS = ('password', 'hash', 'token', 'secret', 'csrf', 'master_key')
_ready = False
_capturing = False


def _now():
    return datetime.now(timezone.utc)


def _stamp(moment=None):
    return (moment or _now()).strftime('%Y-%m-%d %H:%M:%S')


def offset_minutes():
    from config import Config
    try:
        return int(getattr(Config, 'PORTAL_UTC_OFFSET_MINUTES', 330))
    except (TypeError, ValueError):
        return 330


def time_label():
    from config import Config
    return str(getattr(Config, 'PORTAL_TIME_LABEL', 'IST') or 'IST')


def local(moment_text):
    try:
        moment = datetime.strptime(str(moment_text)[:19], '%Y-%m-%d %H:%M:%S')
    except (TypeError, ValueError):
        return str(moment_text or '')
    return (moment + timedelta(minutes=offset_minutes())).strftime('%d %b %Y · %I:%M %p')


def ensure_schema():
    global _ready
    if _ready:
        return
    auto = 'INT AUTO_INCREMENT PRIMARY KEY' if db_pool.is_mysql else 'INTEGER PRIMARY KEY AUTOINCREMENT'
    db_pool.execute_dml(f'''
        CREATE TABLE IF NOT EXISTS {TABLE} (
            activity_id {auto},
            username VARCHAR(100) NOT NULL,
            role VARCHAR(20) NOT NULL,
            action VARCHAR(20) NOT NULL,
            object VARCHAR(120) NOT NULL,
            detail VARCHAR(300) NULL,
            path VARCHAR(200) NULL,
            happened_at VARCHAR(19) NOT NULL,
            address VARCHAR(64) NULL
        )''')
    if db_pool.is_mysql:
        for action in ('UPDATE', 'DELETE'):
            try:
                db_pool.execute_dml(
                    f"CREATE TRIGGER trg_staff_activity_no_{action.lower()} BEFORE {action} "
                    f"ON {TABLE} FOR EACH ROW SIGNAL SQLSTATE '45000' "
                    "SET MESSAGE_TEXT = 'The change log is append-only.'")
            except Exception:
                pass
    else:
        for action in ('UPDATE', 'DELETE'):
            try:
                db_pool.execute_dml(
                    f"CREATE TRIGGER IF NOT EXISTS trg_staff_activity_no_{action.lower()} "
                    f"BEFORE {action} ON {TABLE} BEGIN "
                    "SELECT RAISE(ABORT, 'The change log is append-only.'); END")
            except Exception:
                pass
    _ready = True


# ---------------------------------------------------------------------------
# describing a request
# ---------------------------------------------------------------------------
def _sql_target(statement):
    """The verb and table of a statement typed into the SQL console."""
    text = (statement or '').strip().lstrip('( ')
    verb = text.split()[0].upper() if text else ''
    match = re.search(
        r'\b(?:insert\s+(?:or\s+\w+\s+)?into|replace\s+into|update|delete\s+from)\s+'
        r'["`\[]?([A-Za-z_][A-Za-z0-9_]*)', statement or '', re.I)
    return verb, (match.group(1).lower() if match else '')


def object_for(path):
    for segment, table in OBJECT_BY_PATH.items():
        if f'/{segment}' in path:
            return table
    parts = [part for part in path.split('/') if part]
    return parts[1] if len(parts) > 1 else (parts[0] if parts else 'portal')


def _action_for(method, path):
    if method == 'DELETE' or 'delete' in path or 'remove' in path:
        return 'DELETE'
    if 'update' in path or 'save' in path or 'edit' in path or 'mark' in path:
        return 'UPDATE'
    if 'create' in path or 'add' in path or 'approve' in path or 'pay' in path:
        return 'INSERT'
    return 'POST'


def _clean(value, limit=60):
    text = str(value if value is not None else '').strip().replace('\n', ' ')
    return text if len(text) <= limit else text[:limit - 1] + '…'


def _summary(payload):
    """Field names and short values, with anything secret left out."""
    if not payload:
        return ''
    parts = []
    for key, value in list(payload.items())[:8]:
        lowered = str(key).lower()
        if any(hint in lowered for hint in SECRET_HINTS):
            parts.append(f'{key}=•••')
            continue
        if isinstance(value, (list, dict)):
            parts.append(f'{key}=({len(value)})')
            continue
        parts.append(f'{key}={_clean(value)}')
    extra = len(payload) - 8
    text = ', '.join(parts)
    if extra > 0:
        text += f' +{extra} more'
    return text[:300]


def capture_request(response):
    """Called after every request; records successful admin/faculty changes."""
    global _capturing
    if _capturing:
        return
    try:
        from flask import has_request_context, request, session
        from flask import g
        if not has_request_context():
            return
        if getattr(g, 'activity_skip', False):
            return
        if request.method not in WRITE_METHODS:
            return
        if response is not None and response.status_code >= 400:
            return
        endpoint = request.endpoint or ''
        if endpoint in SKIP_ENDPOINTS or endpoint.startswith('owner.'):
            return
        role = session.get('role')
        username = session.get('username')
        if role not in ROLES or not username:
            return
        if request.path.startswith('/static/'):
            return

        statement = ''
        if endpoint == 'rawdata.query_console':
            statement = (request.form.get('statement') or '').strip()
            action, target = _sql_target(statement)
            if action not in ('INSERT', 'UPDATE', 'DELETE', 'REPLACE'):
                return
            detail = _clean(statement, 280) or 'statement'
            target = target or 'database'
        else:
            payload = request.get_json(silent=True)
            if not isinstance(payload, dict):
                payload = request.form.to_dict(flat=True)
            action = _action_for(request.method, request.path)
            target = object_for(request.path)
            detail = _summary(payload)

        _capturing = True
        try:
            ensure_schema()
            db_pool.execute_dml(
                f'INSERT INTO {TABLE} (username, role, action, object, detail, path, '
                'happened_at, address) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)',
                (username, role, action[:20], str(target)[:120], detail[:300],
                 request.path[:200], _stamp(), (request.remote_addr or '')[:64]))
        finally:
            _capturing = False
    except Exception:
        _capturing = False


# ---------------------------------------------------------------------------
# reading it back
# ---------------------------------------------------------------------------
def _where(username='', role='', action=''):
    clauses, params = [], []
    if username:
        clauses.append('LOWER(username) LIKE LOWER(%s)')
        params.append(f'%{username}%')
    if role:
        clauses.append('role = %s')
        params.append(role)
    if action:
        clauses.append('action = %s')
        params.append(action)
    return (' WHERE ' + ' AND '.join(clauses)) if clauses else '', params


def recent(limit=120, username='', role='', action=''):
    ensure_schema()
    where, params = _where(username, role, action)
    rows = db_pool.execute_query(
        f'SELECT activity_id, username, role, action, object, detail, path, happened_at, '
        f'address FROM {TABLE}{where} ORDER BY activity_id DESC LIMIT %s',
        (*params, int(limit)), fetch='all') or []
    return [{
        'activity_id': row['activity_id'],
        'username': row['username'],
        'role': row['role'],
        'action': row['action'],
        'object': row['object'],
        'detail': row['detail'] or '',
        'path': row['path'] or '',
        'at': local(row['happened_at']),
        'address': row['address'] or '',
    } for row in rows]


def totals():
    ensure_schema()
    total = db_pool.execute_query(f'SELECT COUNT(*) AS n FROM {TABLE}', fetch='one')
    today = db_pool.execute_query(
        f'SELECT COUNT(*) AS n FROM {TABLE} WHERE happened_at >= %s',
        (_stamp(_now().replace(hour=0, minute=0, second=0, microsecond=0)),), fetch='one')
    people = db_pool.execute_query(
        f'SELECT COUNT(DISTINCT username) AS n FROM {TABLE}', fetch='one')
    return {
        'total': int((total or {}).get('n') or 0),
        'today': int((today or {}).get('n') or 0),
        'people': int((people or {}).get('n') or 0),
    }


def as_rows(limit=2000, username='', role='', action=''):
    """Flat rows for the CSV and PDF exports."""
    ensure_schema()
    where, params = _where(username, role, action)
    rows = db_pool.execute_query(
        f'SELECT username, role, action, object, detail, path, happened_at, address '
        f'FROM {TABLE}{where} ORDER BY activity_id DESC LIMIT %s',
        (*params, int(limit)), fetch='all') or []
    return [[row['username'], row['role'], row['action'], row['object'], row['detail'] or '',
             row['path'] or '', local(row['happened_at']), row['address'] or ''] for row in rows]
