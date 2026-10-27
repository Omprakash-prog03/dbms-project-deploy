"""Append-only record of every sign-in and sign-out on the portal.

Whoever signs in — supreme administrator, administrator, faculty member or
student — one row is written with the moment it happened. Whoever signs out
(by themselves, or because the supreme administrator ended their session)
another row is written. Nothing here is ever edited or deleted:

* the table has no UPDATE or DELETE path in the application,
* SQLite triggers abort any UPDATE or DELETE that reaches the database,
* the SQL console refuses to write to it,
* the raw-data viewer only reads it.

The clock is stored in UTC and shown in the portal's timezone
(``PORTAL_UTC_OFFSET_MINUTES``, IST by default), so the times on screen match
the clock on the wall.
"""
from datetime import datetime, timedelta, timezone

from config import Config
from repositories.db_pool import db_pool

TABLE = 'login_history'
SIGNED_IN = 'signed in'
SIGNED_OUT = 'signed out'
_ready = False


def _now():
    return datetime.now(timezone.utc)


def _stamp(moment=None):
    return (moment or _now()).strftime('%Y-%m-%d %H:%M:%S')


def offset_minutes():
    try:
        return int(getattr(Config, 'PORTAL_UTC_OFFSET_MINUTES', 330))
    except (TypeError, ValueError):
        return 330


def time_label():
    return str(getattr(Config, 'PORTAL_TIME_LABEL', 'IST') or 'IST')


def local(moment_text):
    """A stored UTC stamp shown in the portal's timezone."""
    try:
        moment = datetime.strptime(str(moment_text)[:19], '%Y-%m-%d %H:%M:%S')
    except (TypeError, ValueError):
        return str(moment_text or '')
    return (moment + timedelta(minutes=offset_minutes())).strftime('%d %b %Y · %I:%M %p')


def ensure_schema():
    """Create the table and its append-only guards once per process."""
    global _ready
    if _ready:
        return
    auto = 'INT AUTO_INCREMENT PRIMARY KEY' if db_pool.is_mysql else 'INTEGER PRIMARY KEY AUTOINCREMENT'
    db_pool.execute_dml(f'''
        CREATE TABLE IF NOT EXISTS {TABLE} (
            event_id {auto},
            username VARCHAR(100) NOT NULL,
            role VARCHAR(20) NOT NULL,
            event VARCHAR(20) NOT NULL,
            happened_at VARCHAR(19) NOT NULL,
            address VARCHAR(64) NULL,
            detail VARCHAR(200) NULL
        )''')
    # UPDATE/DELETE are refused by the database itself, not only by the app.
    if db_pool.is_mysql:
        for action in ('UPDATE', 'DELETE'):
            try:
                db_pool.execute_dml(
                    f"CREATE TRIGGER trg_login_history_no_{action.lower()} BEFORE {action} "
                    f"ON {TABLE} FOR EACH ROW SIGNAL SQLSTATE '45000' "
                    "SET MESSAGE_TEXT = 'The sign-in history is append-only.'")
            except Exception:
                pass  # already present, or too few privileges: the app still refuses
    else:
        for action in ('UPDATE', 'DELETE'):
            try:
                db_pool.execute_dml(
                    f"CREATE TRIGGER IF NOT EXISTS trg_login_history_no_{action.lower()} "
                    f"BEFORE {action} ON {TABLE} BEGIN "
                    "SELECT RAISE(ABORT, 'The sign-in history is append-only.'); END")
            except Exception:
                pass
    _ready = True


def record(username, role, event, address='', detail=''):
    """Write one line. Never raises: a history problem must not stop a login."""
    name = str(username or '').strip()
    if not name:
        return
    try:
        ensure_schema()
        db_pool.execute_dml(
            f'INSERT INTO {TABLE} (username, role, event, happened_at, address, detail) '
            'VALUES (%s, %s, %s, %s, %s, %s)',
            (name, str(role or 'account'), event, _stamp(),
             str(address or '')[:64], str(detail or '')[:200]))
    except Exception:
        pass


def _where(username='', role='', event=''):
    clauses, params = [], []
    if username:
        clauses.append('LOWER(username) LIKE LOWER(%s)')
        params.append(f'%{username}%')
    if role:
        clauses.append('role = %s')
        params.append(role)
    if event:
        clauses.append('event = %s')
        params.append(event)
    return (' WHERE ' + ' AND '.join(clauses)) if clauses else '', params


def recent(limit=100, username='', role='', event=''):
    """The latest entries, newest first, with a readable local time."""
    ensure_schema()
    where, params = _where(username, role, event)
    rows = db_pool.execute_query(
        f'SELECT event_id, username, role, event, happened_at, address, detail '
        f'FROM {TABLE}{where} ORDER BY event_id DESC LIMIT %s',
        (*params, int(limit)), fetch='all') or []
    return [{
        'event_id': row['event_id'],
        'username': row['username'],
        'role': row['role'],
        'event': row['event'],
        'at': local(row['happened_at']),
        'address': row['address'] or '',
        'detail': row['detail'] or '',
    } for row in rows]


def totals():
    """Small counts for the section heading."""
    ensure_schema()
    total = db_pool.execute_query(f'SELECT COUNT(*) AS n FROM {TABLE}', fetch='one')
    today = db_pool.execute_query(
        f'SELECT COUNT(*) AS n FROM {TABLE} WHERE happened_at >= %s',
        (_stamp(datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)),),
        fetch='one')
    inside = db_pool.execute_query(
        f"SELECT COUNT(*) AS n FROM {TABLE} WHERE event = %s", (SIGNED_IN,), fetch='one')
    outside = db_pool.execute_query(
        f"SELECT COUNT(*) AS n FROM {TABLE} WHERE event = %s", (SIGNED_OUT,), fetch='one')
    return {
        'total': int((total or {}).get('n') or 0),
        'today': int((today or {}).get('n') or 0),
        'signed_in': int((inside or {}).get('n') or 0),
        'signed_out': int((outside or {}).get('n') or 0),
    }
