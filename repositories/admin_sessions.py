"""Live administrator sessions.

Cookie sessions cannot be listed or revoked on their own, so every
administrator sign-in is registered here. Each account carries a
``token_version``; a session remembers the version it was issued at and is
refused the moment the row moves on. That gives the owner three powers:

* sign one administrator out right now,
* sign every other administrator out at once, and
* see who is signed in and when they last did something.

Only the account name, a version number and timestamps are stored — never a
password, a code or a session cookie.
"""
from datetime import datetime, timedelta

from config import Config
from repositories.db_pool import db_pool

TABLE = 'admin_session'
ONLINE_WINDOW_MINUTES = 10
TOUCH_SECONDS = 45
_ready = False


def _now():
    return datetime.utcnow()


def _stamp(moment=None):
    return (moment or _now()).strftime('%Y-%m-%d %H:%M:%S')


def _parse(text):
    try:
        return datetime.strptime(str(text)[:19], '%Y-%m-%d %H:%M:%S')
    except (TypeError, ValueError):
        return None


def ensure_schema():
    global _ready
    if _ready:
        return
    db_pool.execute_dml(f'''
        CREATE TABLE IF NOT EXISTS {TABLE} (
            username VARCHAR(100) PRIMARY KEY,
            token_version INT NOT NULL DEFAULT 1,
            signed_in_at VARCHAR(19) NULL,
            last_seen VARCHAR(19) NULL,
            last_ip VARCHAR(64) NULL,
            login_count INT NOT NULL DEFAULT 0,
            login_blocked INT NOT NULL DEFAULT 0,
            note VARCHAR(200) NULL
        )''')
    _ready = True


def _row(username):
    ensure_schema()
    return db_pool.execute_query(
        f'SELECT * FROM {TABLE} WHERE LOWER(username) = LOWER(%s)', (username,), fetch='one')


def _upsert(username, **fields):
    ensure_schema()
    row = _row(username)
    if not row:
        db_pool.execute_dml(
            f'INSERT INTO {TABLE} (username) VALUES (%s)', (username,))
    if fields:
        assignments = ', '.join(f'{key} = %s' for key in fields)
        db_pool.execute_dml(
            f'UPDATE {TABLE} SET {assignments} WHERE LOWER(username) = LOWER(%s)',
            (*fields.values(), username))


# ---------------------------------------------------------------------------
# signing in and out
# ---------------------------------------------------------------------------
def register(username, ip=''):
    """Record a fresh administrator sign-in and return the version to stamp."""
    _upsert(username, signed_in_at=_stamp(), last_seen=_stamp(), last_ip=ip[:64])
    row = _row(username)
    db_pool.execute_dml(
        f'UPDATE {TABLE} SET login_count = login_count + 1 WHERE LOWER(username) = LOWER(%s)',
        (username,))
    return int(row['token_version'] or 1) if row else 1


def touch(username, ip=''):
    """Mark activity, at most every TOUCH_SECONDS."""
    row = _row(username)
    if not row:
        register(username, ip)
        return
    seen = _parse(row.get('last_seen'))
    if seen and (_now() - seen).total_seconds() < TOUCH_SECONDS:
        return
    _upsert(username, last_seen=_stamp(), last_ip=(ip or row.get('last_ip') or '')[:64])


def version(username):
    row = _row(username)
    return int(row['token_version'] or 1) if row else 1


def sign_out(username):
    """Invalidate every session belonging to one account."""
    row = _row(username)
    if not row:
        return 1
    new_version = int(row['token_version'] or 1) + 1
    _upsert(username, token_version=new_version, last_seen=None)
    return new_version


def sign_out_everyone(except_username):
    """Invalidate every administrator session except the given account."""
    ensure_schema()
    rows = db_pool.execute_query(f'SELECT username FROM {TABLE}', fetch='all') or []
    changed = []
    for row in rows:
        name = row['username']
        if str(name).lower() == str(except_username).lower():
            continue
        sign_out(name)
        changed.append(name)
    return changed


# ---------------------------------------------------------------------------
# the owner's view
# ---------------------------------------------------------------------------
def overview(owner_username):
    """Every administrator account with its live sign-in state."""
    ensure_schema()
    rows = db_pool.execute_query(
        "SELECT user_id, username, role, faculty_id, student_id "
        "FROM app_user WHERE role = 'admin' ORDER BY user_id", fetch='all') or []
    sessions = {str(row['username']).lower(): row
                for row in (db_pool.execute_query(f'SELECT * FROM {TABLE}', fetch='all') or [])}
    now = _now()
    listing = []
    for account in rows:
        name = account['username']
        state = sessions.get(str(name).lower()) or {}
        seen = _parse(state.get('last_seen'))
        signed_in_at = _parse(state.get('signed_in_at'))
        online = bool(seen and (now - seen) <= timedelta(minutes=ONLINE_WINDOW_MINUTES))
        listing.append({
            'username': name,
            'is_owner': str(name).lower() == str(owner_username).lower(),
            'linked': 'faculty' if account.get('faculty_id') else
                      ('student' if account.get('student_id') else ''),
            'signed_in': online,
            'last_seen': state.get('last_seen') or '',
            'last_seen_ago': _ago(seen, now),
            'signed_in_at': signed_in_at.strftime('%Y-%m-%d %H:%M') if signed_in_at else '',
            'login_count': int(state.get('login_count') or 0),
            'blocked': bool(int(state.get('login_blocked') or 0)),
            'last_ip': state.get('last_ip') or '',
            'version': int(state.get('token_version') or 1),
        })
    return listing


def _ago(moment, now):
    if not moment:
        return 'never'
    seconds = int((now - moment).total_seconds())
    if seconds < 60:
        return 'just now'
    if seconds < 3600:
        return f'{seconds // 60} min ago'
    if seconds < 86400:
        return f'{seconds // 3600} h ago'
    return f'{seconds // 86400} d ago'


def summary(owner_username):
    listing = overview(owner_username)
    others = [item for item in listing if not item['is_owner']]
    return {
        'admins': listing,
        'other_count': len(others),
        'online_others': sum(1 for item in others if item['signed_in']),
        'blocked_count': sum(1 for item in others if item['blocked']),
    }


# ---------------------------------------------------------------------------
# blocking
# ---------------------------------------------------------------------------
def block_login(username, blocked, note=''):
    _upsert(username, login_blocked=1 if blocked else 0, note=note[:200] or None)
    if blocked:
        sign_out(username)
    return True


def login_blocked(username):
    row = _row(username)
    return bool(row and int(row.get('login_blocked') or 0))


def is_online(username):
    row = _row(username)
    seen = _parse(row.get('last_seen')) if row else None
    return bool(seen and (_now() - seen) <= timedelta(minutes=ONLINE_WINDOW_MINUTES))


def reset_account(username):
    """Forget a deleted account's session row."""
    ensure_schema()
    db_pool.execute_dml(f'DELETE FROM {TABLE} WHERE LOWER(username) = LOWER(%s)', (username,))
