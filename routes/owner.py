"""Supreme control: the owner's private command centre.

Everything here is owner-only: the master key, the global sign-in switch,
every administrator's live session, one-time access codes, and the account
actions that can remove an administrator entirely.
"""
import secrets

import bcrypt
from flask import (Blueprint, Response, abort, flash, redirect, render_template, request,
                   session, url_for)

from config import Config
from extensions import limiter
from repositories import admin_sessions
from repositories import login_history
from repositories import owner as owner_guard
from repositories import staff_activity
from repositories.db_pool import db_pool
from repositories.pdf import Report
from routes.auth import login_required

owner_bp = Blueprint('owner', __name__)


def _require_owner():
    if session.get('role') != 'admin' or not owner_guard.is_owner(session.get('username')):
        abort(403, description='Only the portal owner can open Supreme control.')


def _key_ok():
    """Step-up check. The master key is optional: when none is set, the
    supreme sign-in is the only lock, and actions are allowed."""
    if not owner_guard.master_key_set():
        return True
    return owner_guard.verify_master_key(request.form.get('master_key', ''))


def _audit_marker():
    return session.get('username', 'owner')


def _role_of(username):
    """The stored role of an account, for the history line."""
    role = db_pool.execute_query(
        'SELECT role FROM app_user WHERE LOWER(username) = LOWER(%s)', (username,), fetch='val')
    if not role:
        return 'admin'
    return 'supreme' if owner_guard.is_owner(username) else str(role)


@owner_bp.route('/supreme')
def supreme_login():
    """The supreme administrator's own door — separate from the campus sign-in."""
    if session.get('role') == 'admin' and owner_guard.is_owner(session.get('username')):
        return redirect(url_for('owner.center'))
    return render_template('supreme_login.html',
                           supreme_name=owner_guard.owner_username())


@owner_bp.route('/supreme/login', methods=['POST'])
@limiter.limit('10 per minute')
def supreme_sign_in():
    """Password-only sign-in for the supreme account, and nobody else."""
    username = (request.form.get('username') or '').strip()
    password = request.form.get('password') or ''
    account = db_pool.execute_query(
        "SELECT user_id, username, password_hash, role FROM app_user "
        "WHERE LOWER(username) = LOWER(%s) AND role = 'admin'", (username,), fetch='one')
    if (not account or not owner_guard.is_owner(account['username'])
            or not _password_ok(account['password_hash'], password)):
        owner_guard.record('supreme sign-in refused', username or 'unknown',
                           f'from {request.remote_addr or "unknown address"}')
        flash('Only the supreme administrator can sign in here.', 'error')
        return redirect(url_for('owner.supreme_login'))

    session.clear()
    session['csrf_token'] = secrets.token_urlsafe(32)
    session.permanent = True
    session['user_id'] = account['user_id']
    session['username'] = account['username']
    session['role'] = 'admin'
    session['access_approved'] = True
    session['supreme'] = True
    session['admin_token_version'] = admin_sessions.register(
        account['username'], request.remote_addr or '')
    owner_guard.stamp_session()
    owner_guard.record('supreme signed in', account['username'],
                       f'from {request.remote_addr or "unknown address"}')
    login_history.record(account['username'], 'supreme', login_history.SIGNED_IN,
                         request.remote_addr or '', 'at the supreme sign-in page')
    return redirect(url_for('owner.center'))


def _password_ok(stored, password):
    if not password or not stored:
        return False
    raw = stored.encode('utf-8') if isinstance(stored, str) else stored
    try:
        return bcrypt.checkpw(password.encode('utf-8'), raw)
    except (ValueError, TypeError):
        return False


@owner_bp.route('/owner')
def center():
    """The supreme space."""
    if 'user_id' not in session:
        return redirect(url_for('owner.supreme_login'))
    _require_owner()
    issued = session.pop('issued_code', None)
    key = session.pop('issued_key', None)
    live = admin_sessions.summary(session.get('username'))
    history_who = (request.args.get('who') or '').strip()
    history_event = (request.args.get('event') or '').strip()
    history_role = (request.args.get('role') or '').strip()
    if history_event not in (login_history.SIGNED_IN, login_history.SIGNED_OUT):
        history_event = ''
    if history_role not in ('supreme', 'admin', 'faculty', 'student'):
        history_role = ''
    exempt = []
    for account in live['admins']:
        account['no_code'] = owner_guard.is_otp_exempt(account['username'])
        if account['no_code'] and not account['is_owner']:
            exempt.append(account['username'])
    return render_template(
        'owner/center.html',
        key_set=owner_guard.master_key_set(),
        key_hint=owner_guard.master_key_hint(),
        epoch=owner_guard.epoch(),
        issued=issued,
        issued_key=key,
        admins=live['admins'],
        no_code_names=', '.join(exempt),
        other_count=live['other_count'],
        online_others=live['online_others'],
        blocked_count=live['blocked_count'],
        pending=owner_guard.pending_requests(),
        logins_closed=owner_guard.login_closed(),
        trail=owner_guard.trail(limit=12),
        history=login_history.recent(limit=120, username=history_who,
                                     role=history_role, event=history_event),
        activity=staff_activity.recent(limit=120, username=_arg('who'),
                                       role=_arg('role'), action=_arg('action')),
        activity_totals=staff_activity.totals(),
        activity_who=_arg('who'),
        activity_role=_arg('role'),
        activity_action=_arg('action'),
        activity_time_label=staff_activity.time_label(),
        history_totals=login_history.totals(),
        history_who=history_who,
        history_event=history_event,
        history_role=history_role,
        history_time_label=login_history.time_label(),
        code_minutes=owner_guard.CODE_MINUTES,
        min_key_length=owner_guard.MIN_MASTER_KEY,
        online_window=admin_sessions.ONLINE_WINDOW_MINUTES,
        portal=Config.PORTAL_NAME,
    )


@owner_bp.route('/admin-access')
@login_required
def owner_view():
    """Old address, kept working."""
    _require_owner()
    return redirect(url_for('owner.center'))


@owner_bp.route('/owner/lockdown', methods=['POST'])
@login_required
@limiter.limit('10 per minute')
def lockdown():
    _require_owner()
    if not _key_ok():
        flash('That master key is not correct, so nobody was signed out.', 'error')
        return redirect(url_for('owner.center'))
    ended_now = admin_sessions.live_usernames(session.get('username'))
    new_epoch = owner_guard.lockdown(session.get('username'))
    for name in ended_now:
        login_history.record(name, _role_of(name), login_history.SIGNED_OUT,
                             request.remote_addr or '',
                             'ended by the supreme administrator (sign out everyone else)')
    session['admin_token_version'] = admin_sessions.version(session.get('username'))
    owner_guard.stamp_session()
    flash(f'Every other administrator has been signed out. You are the only admin signed in '
          f'(lock #{new_epoch}).', 'success')
    return redirect(url_for('owner.center'))


@owner_bp.route('/owner/sign-out/<username>', methods=['POST'])
@login_required
@limiter.limit('30 per minute')
def sign_out_admin(username):
    _require_owner()
    if owner_guard.is_owner(username):
        flash('You cannot sign yourself out from here — use Sign out in the sidebar.', 'error')
        return redirect(url_for('owner.center'))
    admin_sessions.sign_out(username)
    login_history.record(username, _role_of(username), login_history.SIGNED_OUT,
                         request.remote_addr or '',
                         f'ended by the supreme administrator ({_audit_marker()})')
    owner_guard.record('administrator signed out', _audit_marker(), username)
    flash(f'{username} was signed out. Their next click returns them to the sign-in page.', 'success')
    return redirect(url_for('owner.center'))


@owner_bp.route('/owner/switch-logins', methods=['POST'])
@login_required
@limiter.limit('10 per minute')
def switch_logins():
    _require_owner()
    if not _key_ok():
        flash('Enter your master key to change the sign-in switch.', 'error')
        return redirect(url_for('owner.center'))
    closed = request.form.get('closed') == '1'
    owner_guard.close_logins(closed, _audit_marker())
    if closed:
        for name in admin_sessions.live_usernames(session.get('username')):
            login_history.record(name, _role_of(name), login_history.SIGNED_OUT,
                                 request.remote_addr or '',
                                 'administrator sign-in was closed by the supreme administrator')
        admin_sessions.sign_out_everyone(session.get('username'))
    flash('Administrator sign-in is now CLOSED. Only you can sign in.' if closed
          else 'Administrator sign-in is open again.', 'success')
    return redirect(url_for('owner.center'))


@owner_bp.route('/owner/block/<username>', methods=['POST'])
@login_required
@limiter.limit('30 per minute')
def block_admin(username):
    _require_owner()
    if owner_guard.is_owner(username):
        flash('The owner account cannot be blocked.', 'error')
        return redirect(url_for('owner.center'))
    blocked = request.form.get('blocked') == '1'
    owner_guard.block_account(username, blocked, _audit_marker())
    flash(f'{username} is now {"blocked" if blocked else "allowed"} to request access.' if username
          else 'Account updated.', 'success')
    return redirect(url_for('owner.center'))


@owner_bp.route('/owner/master-key', methods=['POST'])
@login_required
@limiter.limit('10 per minute')
def master_key():
    _require_owner()
    if owner_guard.master_key_set() and not _key_ok():
        flash('Enter the current master key before changing it.', 'error')
        return redirect(url_for('owner.center'))
    new_key = request.form.get('new_key', '').strip() or owner_guard.generate_master_key()
    if len(new_key) < owner_guard.MIN_MASTER_KEY:
        flash(f'Use at least {owner_guard.MIN_MASTER_KEY} characters.', 'error')
        return redirect(url_for('owner.center'))
    owner_guard.set_master_key(new_key, rotated_by=_audit_marker())
    session['issued_key'] = new_key
    flash('Your master key is ready. Write it down — it is only shown once.', 'success')
    return redirect(url_for('owner.center'))


@owner_bp.route('/owner/issue', methods=['POST'])
@login_required
@limiter.limit('30 per minute')
def issue():
    _require_owner()
    if not _key_ok():
        flash('Enter your master key to issue an access code.', 'error')
        return redirect(url_for('owner.center'))
    try:
        result = owner_guard.issue_code(request.form.get('request_id', type=int))
    except ValueError as error:
        flash(str(error), 'error')
        return redirect(url_for('owner.center'))
    session['issued_code'] = result
    flash(f'Access code issued for {result["username"]}. It works once and expires in '
          f'{result["minutes"]} minutes.', 'success')
    return redirect(url_for('owner.center'))


@owner_bp.route('/owner/revoke', methods=['POST'])
@login_required
def revoke():
    _require_owner()
    owner_guard.revoke(request.form.get('request_id', type=int))
    flash('Access request closed.', 'info')
    return redirect(url_for('owner.center'))


@owner_bp.route('/owner/reset-password', methods=['POST'])
@login_required
@limiter.limit('20 per minute')
def reset_admin_password():
    """Set a new password for an administrator and end their sessions."""
    _require_owner()
    username = request.form.get('username', '').strip()
    new_password = request.form.get('new_password', '')
    if not _key_ok():
        flash('Enter your master key to change an administrator password.', 'error')
        return redirect(url_for('owner.center'))
    if len(new_password) < 8 or len(new_password.encode('utf-8')) > 72:
        flash('Use at least 8 characters and at most 72 UTF-8 bytes.', 'error')
        return redirect(url_for('owner.center'))
    target = db_pool.execute_query(
        "SELECT user_id FROM app_user WHERE LOWER(username) = LOWER(%s) AND role = 'admin'",
        (username,), fetch='one')
    if not target:
        flash('That administrator account no longer exists.', 'error')
        return redirect(url_for('owner.center'))
    digest = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    db_pool.execute_dml('UPDATE app_user SET password_hash = %s WHERE user_id = %s',
                        (digest, target['user_id']))
    admin_sessions.sign_out(username)
    login_history.record(username, _role_of(username), login_history.SIGNED_OUT,
                         request.remote_addr or '',
                         'password reset by the supreme administrator')
    owner_guard.record('administrator password reset', _audit_marker(), username)
    flash(f'Password changed for {username} and their sessions were ended.', 'success')
    return redirect(url_for('owner.center'))


@owner_bp.route('/owner/remove/<username>', methods=['POST'])
@login_required
@limiter.limit('10 per minute')
def remove_admin(username):
    """Take administrator rights away; the account survives as faculty/student."""
    _require_owner()
    if owner_guard.is_owner(username):
        flash('The owner account cannot be removed.', 'error')
        return redirect(url_for('owner.center'))
    if not _key_ok():
        flash('Enter your master key to remove an administrator.', 'error')
        return redirect(url_for('owner.center'))
    account = db_pool.execute_query(
        "SELECT user_id, faculty_id, student_id FROM app_user "
        "WHERE LOWER(username) = LOWER(%s) AND role = 'admin'", (username,), fetch='one')
    if not account:
        flash('That administrator account no longer exists.', 'error')
        return redirect(url_for('owner.center'))
    if account.get('faculty_id'):
        db_pool.execute_dml("UPDATE app_user SET role = 'faculty' WHERE user_id = %s",
                            (account['user_id'],))
        outcome = 'moved to a faculty account'
    elif account.get('student_id'):
        db_pool.execute_dml("UPDATE app_user SET role = 'student' WHERE user_id = %s",
                            (account['user_id'],))
        outcome = 'moved to a student account'
    else:
        db_pool.execute_dml('DELETE FROM app_user WHERE user_id = %s', (account['user_id'],))
        outcome = 'deleted'
    admin_sessions.reset_account(username)
    login_history.record(username, 'admin', login_history.SIGNED_OUT,
                         request.remote_addr or '',
                         f'account removed by the supreme administrator ({outcome})')
    owner_guard.record('administrator removed', _audit_marker(), f'{username} ({outcome})')
    flash(f'{username} is no longer an administrator ({outcome}).', 'success')
    return redirect(url_for('owner.center'))


# ---------------------------------------------------------------------------
# downloads: the two registers, as CSV and PDF
# ---------------------------------------------------------------------------
HISTORY_HEADERS = ['When', 'Who', 'Role', 'Event', 'From', 'Note']
ACTIVITY_HEADERS = ['When', 'Who', 'Role', 'Action', 'What', 'Details', 'Page', 'From']


def _history_rows():
    return [[row['at'], row['username'], row['role'], row['event'],
             row['address'], row['detail']]
            for row in login_history.recent(limit=5000, username=_arg('who'),
                                            role=_arg('role'), event=_arg('event'))]


def _activity_rows():
    return staff_activity.as_rows(limit=5000, username=_arg('who'),
                                  role=_arg('role'), action=_arg('action'))


def _arg(name):
    return (request.args.get(name) or '').strip()


def _csv_response(filename, headers, rows):
    import csv
    import io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([_csv_safe(cell) for cell in row])
    return Response(output.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition': f'attachment; filename={filename}'})


def _csv_safe(value):
    text = '' if value is None else str(value)
    return "'" + text if text.lstrip().startswith(('=', '+', '-', '@', '\t', '\r')) else text


def _pdf_bytes(title, subtitle, headers, rows, widths):
    report = Report(title, subtitle, landscape=True)
    report.table(headers, rows, widths=widths)
    report.paragraph('Written automatically by the portal. Entries are append-only: they '
                     'cannot be edited or deleted, not even from the SQL console.')
    return report.to_bytes()


@owner_bp.route('/owner/history.csv')
@login_required
def history_csv():
    _require_owner()
    return _csv_response('nist_sign_in_history.csv', HISTORY_HEADERS, _history_rows())


@owner_bp.route('/owner/history.pdf')
@login_required
def history_pdf():
    _require_owner()
    totals = login_history.totals()
    payload = _pdf_bytes(f'{Config.PORTAL_NAME} - Sign-in history',
                         f'{totals["total"]:,} events | shown in {login_history.time_label()}',
                         HISTORY_HEADERS, _history_rows(), widths=[2.1, 1.5, 0.9, 1.1, 1.3, 3.1])
    return Response(payload, mimetype='application/pdf', headers={
        'Content-Disposition': 'attachment; filename=nist_sign_in_history.pdf'})


@owner_bp.route('/owner/activity.csv')
@login_required
def activity_csv():
    _require_owner()
    return _csv_response('nist_change_log.csv', ACTIVITY_HEADERS, _activity_rows())


@owner_bp.route('/owner/activity.pdf')
@login_required
def activity_pdf():
    _require_owner()
    totals = staff_activity.totals()
    payload = _pdf_bytes(f'{Config.PORTAL_NAME} - Change log',
                         f'{totals["total"]:,} changes by administrators and faculty | '
                         f'shown in {staff_activity.time_label()}',
                         ACTIVITY_HEADERS, _activity_rows(),
                         widths=[1.9, 1.3, 0.7, 0.8, 1.5, 3.0, 1.6, 1.1])
    return Response(payload, mimetype='application/pdf', headers={
        'Content-Disposition': 'attachment; filename=nist_change_log.pdf'})
