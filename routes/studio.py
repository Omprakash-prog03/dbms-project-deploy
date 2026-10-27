"""SQL Studio: the administrator's desktop client for the portal database.

The workshop page explains; this page is the tool an administrator would use —
navigator, worksheets, a worksheet editor, a result grid, script output, an
execution plan and a status bar.

The window is **linked to the portal**: a row inserted here is the row the
Students screen shows on its next load, and a table created here appears in Raw
data. Every statement that writes is snapshotted first so it can be undone, and
the portal's own tables cannot be dropped or altered from this client. The
second connection (`ORACLE_XE`) stays a separate, writable practice schema.
"""
from flask import Blueprint, abort, g, jsonify, render_template, request

from repositories import oracle, studio
from routes.auth import login_required, role_required

studio_bp = Blueprint('studio', __name__)

# The menus are data, so the template stays a template and the client stays one
# place: (label, shortcut, action) with a bare None for a separator.
MENUS = [
    ('File', [
        ('New worksheet', 'Ctrl+T', 'new-worksheet'),
        ('Duplicate worksheet', '', 'duplicate-worksheet'),
        ('Rename worksheet', '', 'rename-worksheet'),
        ('Close worksheet', 'Ctrl+W', 'close-worksheet'),
        None,
        ('Save results as CSV', '', 'download-csv'),
        ('Copy results as CSV', '', 'copy-csv'),
    ]),
    ('Edit', [
        ('Undo', 'Ctrl+Z', 'undo'),
        ('Redo', 'Ctrl+Y', 'redo'),
        None,
        ('Undo last database change', 'Ctrl+Alt+Z', 'undo-change'),
        ('Redo database change', 'Ctrl+Alt+Y', 'redo-change'),
        None,
        ('Select all', 'Ctrl+A', 'select-all'),
        ('Copy worksheet', 'Ctrl+C', 'copy-sql'),
        None,
        ('Comment lines', 'Ctrl+/', 'comment'),
        ('Uncomment lines', '', 'uncomment'),
    ]),
    ('Worksheet', [
        ('Run statement', 'F9', 'run-statement'),
        ('Run script', 'F5', 'run-script'),
        ('Explain plan', 'F10', 'explain'),
        None,
        ('Format', '', 'format'),
        ('Clear worksheet', '', 'clear'),
        None,
        ('Snippets', '', 'snippets'),
        ('Statement history', '', 'history'),
    ]),
    ('Tools', [
        ('Object details', '', 'describe'),
        ('Connection information', '', 'connection-info'),
        ('Oracle practice schema', '', 'oracle-info'),
        ('Undo practice change', 'Ctrl+Alt+Z', 'oracle-undo'),
        ('Redo practice change', 'Ctrl+Alt+Y', 'oracle-redo'),
        ('Collapse navigator', '', 'collapse-tree'),
        ('Expand navigator', '', 'expand-tree'),
    ]),
    ('Help', [
        ('Guided tour', '', 'tour'),
        ('Keyboard shortcuts', 'F1', 'shortcuts'),
        ('What this window may change', '', 'read-only-notice'),
        None,
        ('About SQL Studio', '', 'about'),
    ]),
]

# Typing in the editor is not a change to the portal; keep the runs out of the
# change log, exactly like the workshop.
def _skip_activity():
    g.activity_skip = True


@studio_bp.route('/studio')
@login_required
@role_required('admin')
def workspace():
    """The studio screen: everything the client needs, rendered server-side."""
    catalogue = studio.catalogue()
    practice = oracle.catalogue()
    return render_template(
        'studio/index.html',
        connection=studio.connection(),
        catalogue=catalogue,
        snippets=studio.snippets(),
        starter=studio.starter_script(),
        menus=MENUS,
        table_count=len(catalogue['tables']),
        view_count=len(catalogue['views']),
        index_count=len(catalogue['indexes']),
        trigger_count=len(catalogue['triggers']),
        oracle_connection=oracle.connection(),
        oracle_catalogue=practice,
        oracle_starter=oracle.STARTER,
        oracle_snippets=oracle.SNIPPETS,
        oracle_tables=len(practice['tables']),
        oracle_views=len(practice['views']),
        oracle_sequences=len(practice['sequences']),
        oracle_journal=oracle.journal_state(),
        portal_journal=studio.journal_state(),
        portal_base_tables=studio.portal_tables(),
        studio_created=sorted(studio.studio_created()),
    )


@studio_bp.route('/studio/run', methods=['POST'])
@login_required
@role_required('admin')
def run_statement():
    _skip_activity()
    payload = request.get_json(silent=True) or {}
    sql = payload.get('sql')
    if not isinstance(sql, str):
        return jsonify(ok=False, error='Send the worksheet text as "sql".'), 400
    return jsonify(studio.run(sql))


@studio_bp.route('/studio/script', methods=['POST'])
@login_required
@role_required('admin')
def run_script():
    _skip_activity()
    payload = request.get_json(silent=True) or {}
    sql = payload.get('sql')
    if not isinstance(sql, str):
        return jsonify(ok=False, error='Send the worksheet text as "sql".'), 400
    return jsonify(studio.run_script(sql))


@studio_bp.route('/studio/explain', methods=['POST'])
@login_required
@role_required('admin')
def explain():
    _skip_activity()
    payload = request.get_json(silent=True) or {}
    sql = payload.get('sql')
    if not isinstance(sql, str):
        return jsonify(ok=False, error='Send the statement as "sql".'), 400
    return jsonify(studio.explain(sql))


@studio_bp.route('/studio/tree')
@login_required
@role_required('admin')
def tree():
    """The portal navigator, re-read after a structural change."""
    catalogue = studio.catalogue()
    created = sorted(studio.studio_created())
    tree_html = render_template(
        'studio/_tree_portal.html',
        connection=studio.connection(),
        catalogue=catalogue,
        table_count=len(catalogue['tables']),
        view_count=len(catalogue['views']),
        index_count=len(catalogue['indexes']),
        studio_created=created,
    )
    return jsonify(ok=True, catalogue=catalogue, journal=studio.journal_state(),
                   created=created, tree_html=tree_html)


@studio_bp.route('/studio/undo', methods=['POST'])
@login_required
@role_required('admin')
def undo():
    """Put the portal database back as it was before the last studio change."""
    return jsonify(studio.undo())


@studio_bp.route('/studio/redo', methods=['POST'])
@login_required
@role_required('admin')
def redo():
    """Replay the portal change that undo took back."""
    return jsonify(studio.redo())


@studio_bp.route('/studio/describe/<name>')
@login_required
@role_required('admin')
def describe(name):
    _skip_activity()
    details = studio.describe(name)
    if not details.get('ok'):
        abort(404, description=details.get('error'))
    return jsonify(details)


# ---------------------------------------------------------------------------
# the Oracle practice connection
# ---------------------------------------------------------------------------
@studio_bp.route('/studio/oracle/run', methods=['POST'])
@login_required
@role_required('admin')
def oracle_run():
    _skip_activity()
    payload = request.get_json(silent=True) or {}
    sql = payload.get('sql')
    if not isinstance(sql, str):
        return jsonify(ok=False, error='Send the worksheet text as "sql".'), 400
    return jsonify(oracle.run(sql))


@studio_bp.route('/studio/oracle/script', methods=['POST'])
@login_required
@role_required('admin')
def oracle_script():
    _skip_activity()
    payload = request.get_json(silent=True) or {}
    sql = payload.get('sql')
    if not isinstance(sql, str):
        return jsonify(ok=False, error='Send the worksheet text as "sql".'), 400
    return jsonify(oracle.run_script(sql))


@studio_bp.route('/studio/oracle/explain', methods=['POST'])
@login_required
@role_required('admin')
def oracle_explain():
    _skip_activity()
    payload = request.get_json(silent=True) or {}
    sql = payload.get('sql')
    if not isinstance(sql, str):
        return jsonify(ok=False, error='Send the statement as "sql".'), 400
    return jsonify(oracle.explain(sql))


@studio_bp.route('/studio/oracle/tree')
@login_required
@role_required('admin')
def oracle_tree():
    """The navigator after DDL: the practice schema, as it stands now."""
    _skip_activity()
    return jsonify(ok=True, catalogue=oracle.catalogue(), connection=oracle.connection(),
                   journal=oracle.journal_state())


@studio_bp.route('/studio/oracle/undo', methods=['POST'])
@login_required
@role_required('admin')
def oracle_undo():
    """Put the practice schema back the way it was before the last change."""
    _skip_activity()
    return jsonify(oracle.undo())


@studio_bp.route('/studio/oracle/redo', methods=['POST'])
@login_required
@role_required('admin')
def oracle_redo():
    """Replay the change that undo took back."""
    _skip_activity()
    return jsonify(oracle.redo())


@studio_bp.route('/studio/oracle/reset', methods=['POST'])
@login_required
@role_required('admin')
def oracle_reset():
    """Put the practice schema back to the seeded SCOTT schema."""
    _skip_activity()
    return jsonify(oracle.reset())
