"""Owner guard: one supreme administrator, a master key, and access codes.

The portal can have several administrator accounts, but exactly one of them is
the **owner** — the person who installed it. The owner holds a master key (the
"PIN") that lets them:

* end every other administrator session at once (``lockdown``), and
* issue a one-time access code that another administrator must type before
  their own login is allowed (``issue_code``).

Only hashes are stored. Nothing here ever keeps a master key or an access code
in plaintext, and the tables are created on first use so an existing
installation needs no migration.
"""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

import bcrypt
from flask import g, has_app_context

from config import Config
from repositories import admin_sessions
from repositories.db_pool import db_pool

GUARD_TABLE = 'owner_guard'
REQUEST_TABLE = 'admin_access_request'
CODE_MINUTES = 15
CODE_ATTEMPTS = 5
MIN_MASTER_KEY = 10


def _now():
    return datetime.utcnow()


def _stamp(moment):
    return moment.strftime('%Y-%m-%d %H:%M:%S')


def _parse(text):
    try:
        return datetime.strptime(str(text)[:19], '%Y-%m-%d %H:%M:%S')
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# storage
# ---------------------------------------------------------------------------
_ready = False


def ensure_schema():
    """Create the two guard tables once per process."""
    global _ready
    if _ready:
        return
    auto = 'INT AUTO_INCREMENT PRIMARY KEY' if db_pool.is_mysql else 'INTEGER PRIMARY KEY AUTOINCREMENT'
    db_pool.execute_dml(f'''
        CREATE TABLE IF NOT EXISTS {GUARD_TABLE} (
            guard_key VARCHAR(64) PRIMARY KEY,
            guard_value TEXT NULL
        )''')
    db_pool.execute_dml(f'''
        CREATE TABLE IF NOT EXISTS {REQUEST_TABLE} (
            request_id {auto},
            username VARCHAR(100) NOT NULL,
            user_id INT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            code_hash VARCHAR(255) NULL,
            code_expires VARCHAR(19) NULL,
            attempts INT NOT NULL DEFAULT 0,
            requested_at VARCHAR(19) NULL,
            resolved_at VARCHAR(19) NULL,
            note VARCHAR(200) NULL
        )''')
    _ready = True


def _get(key, default=None):
    ensure_schema()
    value = db_pool.execute_query(
        f'SELECT guard_value FROM {GUARD_TABLE} WHERE guard_key = %s', (key,), fetch='val')
    return default if value is None else value


def _set(key, value):
    ensure_schema()
    changed = db_pool.execute_dml(
        f'UPDATE {GUARD_TABLE} SET guard_value = %s WHERE guard_key = %s', (value, key))
    if not changed.get('rowcount'):
        db_pool.execute_dml(
            f'INSERT INTO {GUARD_TABLE} (guard_key, guard_value) VALUES (%s, %s)', (key, value))


def record(action, who, detail):
    """Public audit entry, used by Supreme control."""
    _record(action, who, detail)


def trail(limit=12):
    """The owner's own recent actions, newest first."""
    ensure_schema()
    try:
        rows = db_pool.execute_query(
            "SELECT action, new_values, changed_by, changed_at FROM audit_log "
            "WHERE table_name = 'admin_guard' ORDER BY changed_at DESC, log_id DESC LIMIT %s",
            (limit,), fetch='all') or []
    except Exception:
        return []
    trail_rows = []
    for row in rows:
        action, _, detail = (row['new_values'] or '').partition(' | ')
        trail_rows.append({'action': action or row['action'] or 'owner action',
                           'detail': detail.strip(),
                           'who': row['changed_by'] or 'owner',
                           'when': row['changed_at']})
    return trail_rows


def _record(action, who, detail):
    """Keep a short trail in the existing audit log."""
    try:
        db_pool.execute_dml(
            "INSERT INTO audit_log (table_name, action, record_id, new_values, changed_by) "
            "VALUES ('admin_guard', 'UPDATE', 0, %s, %s)",
            (f'{action} | {detail}', who))
    except Exception:
        pass


# ---------------------------------------------------------------------------
# who is the owner
# ---------------------------------------------------------------------------
def _memo(name, factory):
    """Cache one value per request; work without a request (scripts) too."""
    if not has_app_context():
        return factory()
    if name not in g:
        setattr(g, name, factory())
    return getattr(g, name)


def owner_username():
    """The supreme administrator: configured value, else the first admin account."""
    return _memo('owner_username', _resolve_owner)


def _admin_exists(username):
    if not username:
        return False
    return bool(db_pool.execute_query(
        "SELECT user_id FROM app_user WHERE LOWER(username) = LOWER(%s) AND role = 'admin'",
        (username,), fetch='one'))


def _resolve_owner():
    """The supreme account, the stored owner, or the first administrator.

    A configured name only counts when that administrator actually exists, so a
    typo in ``OWNER_USERNAME`` can never leave a portal with no owner at all.
    """
    for candidate in (getattr(Config, 'OWNER_USERNAME', ''), _get('owner_username')):
        name = str(candidate or '').strip()
        if name and _admin_exists(name):
            return name.lower()
    fallback = db_pool.execute_query(
        "SELECT username FROM app_user WHERE role = 'admin' ORDER BY user_id LIMIT 1",
        fetch='val') or ''
    return str(fallback).strip().lower()


def is_owner(username):
    return bool(username) and str(username).strip().lower() == owner_username()


# ---------------------------------------------------------------------------
# master key ("the PIN")
# ---------------------------------------------------------------------------
def master_key_set():
    return bool(_get('master_key_hash'))


def master_key_hint():
    """A masked reminder so the owner recognises which key is active."""
    return _get('master_key_preview') or ''


def set_master_key(key, rotated_by=''):
    """Store a new master key. Only a bcrypt hash and a masked hint are kept."""
    key = (key or '').strip()
    if len(key) < MIN_MASTER_KEY:
        raise ValueError(f'Use at least {MIN_MASTER_KEY} characters for the master key.')
    digest = bcrypt.hashpw(key.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    _set('master_key_hash', digest)
    _set('master_key_preview', f'{key[:4]}…{key[-2:]}')
    _set('master_key_set_at', _stamp(_now()))
    _record('master key set', rotated_by or 'owner', 'master key created')
    return True


def verify_master_key(key):
    stored = _get('master_key_hash')
    if not stored or not key:
        return False
    try:
        return bcrypt.checkpw(str(key).strip().encode('utf-8'), stored.encode('utf-8'))
    except (ValueError, TypeError):
        return False


def generate_master_key():
    """A memorable but strong key: four groups of four characters."""
    alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    groups = [''.join(secrets.choice(alphabet) for _ in range(4)) for _ in range(4)]
    return '-'.join(groups)


# ---------------------------------------------------------------------------
# sessions
# ---------------------------------------------------------------------------
def epoch():
    """Monotonic counter. Any administrator session carrying an older value is
    treated as signed out — that is how one click logs everybody else out."""
    def read():
        try:
            return int(_get('epoch', 1) or 1)
        except (TypeError, ValueError):
            return 1
    return _memo('owner_epoch', read)


def lockdown(by_username):
    """Invalidate every administrator session except the caller's."""
    current = epoch()
    new_epoch = current + 1
    _set('epoch', new_epoch)
    _set('epoch_changed_at', _stamp(_now()))
    _set('epoch_changed_by', by_username)
    if has_app_context():
        g.owner_epoch = new_epoch
    ended = admin_sessions.sign_out_everyone(by_username)
    _record('lockdown', by_username,
            f'administrator sessions ended (epoch {current} -> {new_epoch}); {len(ended)} account(s) signed out')
    return new_epoch


def session_is_current():
    """True when this admin session was issued after the last lockdown."""
    return session_epoch() == epoch()


def session_epoch():
    from flask import session
    try:
        return int(session.get('owner_epoch') or 0)
    except (TypeError, ValueError):
        return 0


def stamp_session():
    """Mark the current session as valid for the current lockdown epoch."""
    from flask import session
    session['owner_epoch'] = epoch()


# ---------------------------------------------------------------------------
# access codes (the OTP the owner hands out)
# ---------------------------------------------------------------------------
def _requests(where='', params=()):
    ensure_schema()
    return db_pool.execute_query(
        f'SELECT * FROM {REQUEST_TABLE} {where} ORDER BY request_id DESC', params, fetch='all')


def request_access(username, user_id=None, note=''):
    """Record that an administrator is waiting for the owner's approval."""
    ensure_schema()
    username = str(username).strip()
    existing = _requests('WHERE LOWER(username) = LOWER(%s) AND status IN (%s, %s)',
                         (username, 'pending', 'approved'))
    if existing:
        db_pool.execute_dml(
            f'UPDATE {REQUEST_TABLE} SET requested_at = %s, note = %s WHERE request_id = %s',
            (_stamp(_now()), note[:200], existing[0]['request_id']))
        return existing[0]['request_id']
    db_pool.execute_dml(
        f'INSERT INTO {REQUEST_TABLE} (username, user_id, status, requested_at, note) '
        f'VALUES (%s, %s, %s, %s, %s)',
        (username, user_id, 'pending', _stamp(_now()), note[:200]))
    row = db_pool.execute_query(
        f'SELECT request_id FROM {REQUEST_TABLE} WHERE LOWER(username) = LOWER(%s) '
        'ORDER BY request_id DESC LIMIT 1', (username,), fetch='val')
    _record('access requested', username, 'asked for a one-time code')
    return row


def pending_requests():
    """Requests the owner still has to act on, newest first."""
    rows = _requests("WHERE status IN ('pending', 'approved')")
    now = _now()
    for row in rows:
        expires = _parse(row.get('code_expires'))
        row['expired'] = bool(expires and expires < now)
        row['waiting_minutes'] = 0
        requested = _parse(row.get('requested_at'))
        if requested:
            row['waiting_minutes'] = max(0, int((now - requested).total_seconds() // 60))
    return rows


def issue_code(request_id):
    """Approve a request and return a single-use six-digit code (shown once)."""
    ensure_schema()
    row = db_pool.execute_query(
        f'SELECT * FROM {REQUEST_TABLE} WHERE request_id = %s', (request_id,), fetch='one')
    if not row:
        raise ValueError('That access request no longer exists.')
    code = f'{secrets.randbelow(1000000):06d}'
    digest = bcrypt.hashpw(code.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    expires = _stamp(_now() + timedelta(minutes=CODE_MINUTES))
    db_pool.execute_dml(
        f'UPDATE {REQUEST_TABLE} SET status = %s, code_hash = %s, code_expires = %s, '
        'attempts = 0, resolved_at = %s WHERE request_id = %s',
        ('approved', digest, expires, _stamp(_now()), request_id))
    _record('access code issued', 'owner', f'code issued for {row["username"]}')
    return {'code': code, 'username': row['username'], 'expires': expires,
            'minutes': CODE_MINUTES, 'request_id': request_id}


def redeem_code(username, code):
    """Check an access code. Single use, 15 minutes, five wrong tries."""
    ensure_schema()
    code = str(code or '').strip()
    if not code:
        return False, 'Enter the access code the owner gave you.'
    rows = _requests("WHERE LOWER(username) = LOWER(%s) AND status = 'approved'", (username,))
    if not rows:
        return False, ('There is no approved access request for this account yet. Ask the owner '
                       'for a code, or use the rotating number shown on the supreme page.')
    row = rows[0]
    expires = _parse(row.get('code_expires'))
    if not expires or expires < _now():
        db_pool.execute_dml(
            f'UPDATE {REQUEST_TABLE} SET status = %s WHERE request_id = %s', ('revoked', row['request_id']))
        return False, 'That access code has expired. Ask the owner for a new one.'
    if int(row.get('attempts') or 0) >= CODE_ATTEMPTS:
        db_pool.execute_dml(
            f'UPDATE {REQUEST_TABLE} SET status = %s WHERE request_id = %s', ('revoked', row['request_id']))
        return False, 'Too many wrong attempts. Ask the owner for a new access code.'
    stored = row.get('code_hash') or ''
    try:
        valid = hmac.compare_digest(
            str(bcrypt.checkpw(code.encode('utf-8'), stored.encode('utf-8'))), 'True')
    except (ValueError, TypeError):
        valid = False
    if not valid:
        attempts = int(row.get('attempts') or 0) + 1
        status = 'revoked' if attempts >= CODE_ATTEMPTS else 'approved'
        db_pool.execute_dml(
            f'UPDATE {REQUEST_TABLE} SET attempts = %s, status = %s WHERE request_id = %s',
            (attempts, status, row['request_id']))
        left = max(0, CODE_ATTEMPTS - attempts)
        return False, f'That access code is not correct. {left} attempt{"" if left == 1 else "s"} left.'
    db_pool.execute_dml(
        f'UPDATE {REQUEST_TABLE} SET status = %s, resolved_at = %s, code_hash = NULL '
        'WHERE request_id = %s', ('used', _stamp(_now()), row['request_id']))
    _record('access granted', username, 'signed in with an access code')
    return True, 'Access granted.'


def requests_for(username):
    """Every access request for one account, newest first."""
    return _requests('WHERE LOWER(username) = LOWER(%s)', (username,))


def pending_count():
    ensure_schema()
    return db_pool.execute_query(
        f"SELECT COUNT(*) FROM {REQUEST_TABLE} WHERE status IN ('pending', 'approved')",
        fetch='val') or 0


def revoke(request_id):
    ensure_schema()
    db_pool.execute_dml(
        f'UPDATE {REQUEST_TABLE} SET status = %s WHERE request_id = %s', ('revoked', request_id))
    _record('access revoked', 'owner', f'request {request_id} revoked')


def otp_exempt_usernames():
    """Administrators who sign in with a password only."""
    raw = str(getattr(Config, 'OTP_EXEMPT_ADMINS', '') or '')
    return {part.strip().lower() for part in raw.replace(';', ',').split(',') if part.strip()}


def is_otp_exempt(username):
    """The supreme administrator, and any admin explicitly exempted."""
    name = str(username or '').strip().lower()
    return bool(name) and (is_owner(name) or name in otp_exempt_usernames())


def code_required():
    """Does an administrator have to type a code at sign-in?

    Off by default: administrators sign in the normal way, with their username
    and password. The supreme administrator can switch the requirement on from
    the supreme page, and switch it off again just as easily.
    """
    return bool(int(_get('code_required', 0) or 0))


def set_code_required(required, by_username='owner'):
    _set('code_required', 1 if required else 0)
    _record('sign-in codes required' if required else 'password-only sign-in',
            by_username, 'administrator sign-in')
    return bool(required)


def needs_approval(username, role):
    """Only when the supreme administrator has asked for codes.

    The switch is off on a normal installation, so username + password is all an
    administrator needs. While it is on, every administrator who is not exempt
    must also supply the rotating number or a one-time code.
    """
    return code_required() and role == 'admin' and not is_otp_exempt(username)


def login_closed():
    """The owner's global switch: no administrator may sign in but them."""
    return bool(int(_get('login_closed', 0) or 0))


def close_logins(closed, by_username='owner'):
    _set('login_closed', 1 if closed else 0)
    _set('login_closed_at', _stamp(_now()))
    _record('logins closed' if closed else 'logins opened', by_username,
            'administrator sign-in switch')
    return closed


def account_blocked(username):
    return admin_sessions.login_blocked(username)


def block_account(username, blocked, by_username='owner'):
    admin_sessions.block_login(username, blocked)
    _record('account blocked' if blocked else 'account unblocked', by_username, username)
    return blocked


def other_admins(username):
    """How many other administrator accounts exist (for the owner's page)."""
    rows = db_pool.execute_query(
        "SELECT username FROM app_user WHERE role = 'admin'", fetch='all') or []
    return [row['username'] for row in rows if not is_owner(row['username'])]


# ---------------------------------------------------------------------------
# the rotating code: one six-digit number, changed every ten minutes
# ---------------------------------------------------------------------------
# Some campus setups do not want a per-person code round trip: the supreme
# administrator keeps one screen open, reads the number off it, and tells the
# administrator who is standing in front of them. The number is derived from an
# installation secret and the clock, so it is never stored, never reused, and it
# changes by itself. It is deliberately *not* the same thing as the one-time
# access code above: the owner can switch it off in one click.
ROTATING_MINUTES = 10


def rotating_minutes():
    """How long one number lasts (minutes). Configurable, ten by default."""
    try:
        value = int(getattr(Config, 'ROTATING_CODE_MINUTES', ROTATING_MINUTES))
    except (TypeError, ValueError):
        return ROTATING_MINUTES
    return value if 1 <= value <= 120 else ROTATING_MINUTES


def _rotating_secret():
    """A per-installation secret, created on first use."""
    secret = _get('rotating_secret')
    if not secret:
        secret = secrets.token_hex(16)
        _set('rotating_secret', secret)
    return secret


def rotating_window(moment=None):
    """Which ten-minute slot a moment falls in."""
    step = rotating_minutes() * 60
    return int((moment or _now()).timestamp()) // step


def rotating_code(window=None):
    """The six-digit number for one slot (the current one by default)."""
    slot = rotating_window() if window is None else int(window)
    digest = hmac.new(_rotating_secret().encode('utf-8'),
                      f'nist-rotating-{slot}'.encode('utf-8'), hashlib.sha256).digest()
    return f'{int.from_bytes(digest[:8], "big") % 1000000:06d}'


def rotating_seconds_left(moment=None):
    """Seconds until the number changes."""
    step = rotating_minutes() * 60
    now = moment or _now()
    return step - (int(now.timestamp()) % step)


def rotating_enabled():
    """Is the rotating code accepted at sign-in? On unless switched off."""
    return bool(int(_get('rotating_enabled', 1) or 0))


def set_rotating_enabled(enabled, by_username='owner'):
    _set('rotating_enabled', 1 if enabled else 0)
    _record('rotating code on' if enabled else 'rotating code off', by_username,
            'administrator sign-in')
    return bool(enabled)


def verify_rotating_code(code, moment=None):
    """Does this six-digit number match, now or in the slot that just ended?

    The previous slot is accepted so a number read a few seconds before the
    change still works while the administrator is typing it.
    """
    text = str(code or '').strip()
    if not rotating_enabled() or len(text) != 6 or not text.isdigit():
        return False
    now = moment or _now()
    windows = (rotating_window(now),
               rotating_window(now - timedelta(minutes=rotating_minutes())))
    return any(hmac.compare_digest(text, rotating_code(window)) for window in windows)


def _portal_clock(moment):
    """A moment as the campus reads it (IST by default), e.g. "04:10 PM IST"."""
    try:
        offset = int(getattr(Config, 'PORTAL_UTC_OFFSET_MINUTES', 330))
    except (TypeError, ValueError):
        offset = 330
    label = str(getattr(Config, 'PORTAL_TIME_LABEL', 'IST') or 'IST')
    return f'{(moment + timedelta(minutes=offset)).strftime("%I:%M %p").lstrip("0")} {label}'


def rotating_snapshot(moment=None):
    """Everything the supreme page and the sign-in page need to know."""
    now = moment or _now()
    minutes = rotating_minutes()
    changes_at = now + timedelta(seconds=rotating_seconds_left(now))
    return {
        'code': rotating_code(rotating_window(now)),
        'minutes': minutes,
        'seconds_left': rotating_seconds_left(now),
        'enabled': rotating_enabled(),
        'next_change': _stamp(changes_at),
        'next_change_label': _portal_clock(changes_at),
    }


def close_request(request_id, note='closed by the owner'):
    """Mark a request handled without issuing a code (used by the rotating path)."""
    ensure_schema()
    db_pool.execute_dml(
        f'UPDATE {REQUEST_TABLE} SET status = %s, resolved_at = %s WHERE request_id = %s',
        ('used', _stamp(_now()), request_id))
    _record('access granted', 'rotating code', note)
