"""Owner controls: master key, lockdown, and administrator access codes."""
from flask import (Blueprint, flash, redirect, render_template, request, session, url_for)

from extensions import limiter
from repositories import owner as owner_guard
from routes.auth import login_required

owner_bp = Blueprint('owner', __name__)


def _owner_only():
    """Only the supreme administrator may see or use these controls."""
    if session.get('role') != 'admin' or not owner_guard.is_owner(session.get('username')):
        return False
    return True


@owner_bp.route('/admin-access')
@login_required
def owner_view():
    if not _owner_only():
        from flask import abort
        abort(403, description='Only the portal owner can open this page.')
    issued = session.pop('issued_code', None)
    return render_template(
        'owner/index.html',
        key_set=owner_guard.master_key_set(),
        key_hint=owner_guard.master_key_hint(),
        epoch=owner_guard.epoch(),
        pending=owner_guard.pending_requests(),
        other_admins=owner_guard.other_admins(session.get('username')),
        issued=issued,
        code_minutes=owner_guard.CODE_MINUTES,
        min_key_length=owner_guard.MIN_MASTER_KEY,
    )


@owner_bp.route('/admin-access/lockdown', methods=['POST'])
@login_required
@limiter.limit('10 per minute')
def lockdown():
    if not _owner_only():
        from flask import abort
        abort(403, description='Only the portal owner can lock the console.')
    if not owner_guard.verify_master_key(request.form.get('master_key', '')):
        flash('That master key is not correct, so nobody was signed out.', 'error')
        return redirect(url_for('owner.owner_view'))
    new_epoch = owner_guard.lockdown(session.get('username'))
    owner_guard.stamp_session()  # the caller stays signed in
    flash(f'Every other administrator session has been ended. You are the only admin signed in (lock #{new_epoch}).', 'success')
    return redirect(url_for('owner.owner_view'))


@owner_bp.route('/admin-access/master-key', methods=['POST'])
@login_required
@limiter.limit('10 per minute')
def master_key():
    if not _owner_only():
        from flask import abort
        abort(403, description='Only the portal owner can change the master key.')
    action = request.form.get('action', 'generate')
    if owner_guard.master_key_set():
        if not owner_guard.verify_master_key(request.form.get('master_key', '')):
            flash('Enter the current master key before changing it.', 'error')
            return redirect(url_for('owner.owner_view'))
        new_key = request.form.get('new_key', '').strip() or owner_guard.generate_master_key()
        owner_guard.set_master_key(new_key, rotated_by=session.get('username', 'owner'))
        session['issued_key'] = new_key
        flash('A new master key was created. Save it now — it is only shown once.', 'success')
        return redirect(url_for('owner.owner_view'))
    new_key = request.form.get('new_key', '').strip() or owner_guard.generate_master_key()
    owner_guard.set_master_key(new_key, rotated_by=session.get('username', 'owner'))
    session['issued_key'] = new_key
    flash('Your master key is ready. Write it down — it is only shown once.', 'success')
    return redirect(url_for('owner.owner_view'))


@owner_bp.route('/admin-access/issue', methods=['POST'])
@login_required
@limiter.limit('20 per minute')
def issue():
    if not _owner_only():
        from flask import abort
        abort(403, description='Only the portal owner can issue access codes.')
    if not owner_guard.verify_master_key(request.form.get('master_key', '')):
        flash('Enter your master key to issue an access code.', 'error')
        return redirect(url_for('owner.owner_view'))
    try:
        result = owner_guard.issue_code(request.form.get('request_id', type=int))
    except ValueError as error:
        flash(str(error), 'error')
        return redirect(url_for('owner.owner_view'))
    session['issued_code'] = result
    flash(f'Access code issued for {result["username"]}. It works once and expires in {result["minutes"]} minutes.', 'success')
    return redirect(url_for('owner.owner_view'))


@owner_bp.route('/admin-access/revoke', methods=['POST'])
@login_required
def revoke():
    if not _owner_only():
        from flask import abort
        abort(403, description='Only the portal owner can revoke access.')
    owner_guard.revoke(request.form.get('request_id', type=int))
    flash('Access request closed.', 'info')
    return redirect(url_for('owner.owner_view'))
