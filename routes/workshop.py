"""The database workshop: one admin-only page that shows how the database works.

Every tab is backed by the running database rather than by a screenshot: the joins
are executed, the views are read from the engine's catalogue, the triggers are listed
with their real bodies, the procedures are walked through read-only, and the plans
come from the engine's own optimiser. Nothing on this page writes a row.
"""
from flask import (Blueprint, Response, abort, g, jsonify, render_template, request,
                   session)

from repositories import workshop
from repositories.pdf import Report
from routes.auth import login_required, role_required

workshop_bp = Blueprint('workshop', __name__)

TABS = [
    ('overview', 'How it works'),
    ('joins', 'Joins'),
    ('views', 'Views'),
    ('procedures', 'Procedures'),
    ('functions', 'Functions'),
    ('triggers', 'Triggers'),
    ('plans', 'Execution plans'),
    ('schema', 'Schema & storage'),
]
TAB_KEYS = [key for key, _ in TABS]


def _no_activity_log():
    """Demonstrations are rolled back, so they must not reach the change log."""
    g.activity_skip = True


@workshop_bp.route('/database')
@login_required
@role_required('admin')
def index():
    tab = (request.args.get('tab') or 'overview').strip()
    if tab not in TAB_KEYS:
        tab = 'overview'
    selected = (request.args.get('item') or '').strip()

    context = {
        'tab': tab,
        'tabs': TABS,
        'selected': selected,
        'overview': workshop.overview(),
        'primer': workshop.primer(),
        'demos': workshop.join_demos(),
        'views_catalogue': [],
        'procedures': [],
        'functions_catalogue': [],
        'trigger_groups': [],
        'trigger_proofs': workshop.TRIGGER_PROOFS,
        'schema_tables': [],
        'indexes': [],
        'storage': workshop.storage(),
        'demo_result': None,
        'demo': None,
        'plan': None,
        'dry_run': None,
        'function_result': None,
        'function_demo': None,
    }

    if tab == 'joins':
        demo = workshop.join_demo(selected) or (context['demos'][0] if context['demos'] else None)
        context['demo'] = demo
        if demo:
            context['demo_result'] = workshop.run_demo(demo['key'])
            context['plan'] = workshop.explain_demo(demo['key'])
    elif tab == 'views':
        context['views_catalogue'] = workshop.views()
        if selected:
            chosen = next((view for view in context['views_catalogue']
                           if view['name'] == selected), None)
            context['view_item'] = chosen
    elif tab == 'procedures':
        context['procedures'] = workshop.procedures()
        chosen = next((item for item in context['procedures'] if item['name'] == selected), None)
        if not chosen and context['procedures']:
            chosen = context['procedures'][0]
        context['procedure_item'] = chosen
        if chosen:
            context['dry_run'] = workshop.procedure_dry_run(chosen['name'])
    elif tab == 'functions':
        context['functions_catalogue'] = workshop.functions()
        chosen = next((item for item in context['functions_catalogue']
                       if item['name'] == selected), None)
        if not chosen and context['functions_catalogue']:
            chosen = context['functions_catalogue'][0]
        context['function_item'] = chosen
        if chosen and chosen.get('demo'):
            context['function_result'] = workshop.evaluate_function(chosen['demo'])
            context['function_demo'] = chosen['demo']
    elif tab == 'triggers':
        context['trigger_groups'] = workshop.trigger_groups()
        context['trigger_count'] = sum(len(group['triggers'])
                                       for group in context['trigger_groups'])
    elif tab == 'plans':
        context['plans'] = [{'demo': demo, 'plan': workshop.explain_demo(demo['key'])}
                            for demo in workshop.join_demos()]
    elif tab == 'schema':
        context['schema_tables'] = workshop.schema()
        context['indexes'] = workshop.indexes()

    return render_template('workshop/index.html', **context)


# ---------------------------------------------------------------------------
# live endpoints (the buttons on the page)
# ---------------------------------------------------------------------------
@workshop_bp.route('/database/run/<key>', methods=['POST'])
@login_required
@role_required('admin')
def run(key):
    _no_activity_log()
    if not workshop.join_demo(key):
        return jsonify(ok=False, error='Unknown demonstration.'), 404
    return jsonify(workshop.run_demo(key))


@workshop_bp.route('/database/explain/<key>', methods=['POST'])
@login_required
@role_required('admin')
def explain(key):
    _no_activity_log()
    if not workshop.join_demo(key):
        return jsonify(ok=False, error='Unknown demonstration.'), 404
    return jsonify(workshop.explain_demo(key))


@workshop_bp.route('/database/function/<key>', methods=['POST'])
@login_required
@role_required('admin')
def function(key):
    _no_activity_log()
    if key not in {item['demo'] for item in workshop.functions()}:
        return jsonify(ok=False, error='Unknown function.'), 404
    return jsonify(workshop.evaluate_function(key))


@workshop_bp.route('/database/procedure/<name>', methods=['POST'])
@login_required
@role_required('admin')
def procedure(name):
    _no_activity_log()
    if name not in {item['name'] for item in workshop.procedures()}:
        return jsonify(ok=False, error='Unknown procedure.'), 404
    return jsonify(workshop.procedure_dry_run(name))


@workshop_bp.route('/database/prove/<rule>', methods=['POST'])
@login_required
@role_required('admin')
def prove(rule):
    _no_activity_log()
    if rule not in {proof['rule'] for proof in workshop.TRIGGER_PROOFS}:
        return jsonify(ok=False, refused=False, error='Unknown rule.'), 404
    return jsonify(workshop.prove(rule))


# ---------------------------------------------------------------------------
# the printable handout
# ---------------------------------------------------------------------------
@workshop_bp.route('/database/workshop.pdf')
@login_required
@role_required('admin')
def handout():
    """A one-file PDF of the whole workshop — for a viva, or for the sir."""
    facts = workshop.storage()
    report = Report('Database workshop',
                    f"NIST University Portal Management · {facts.get('engine')} "
                    f"{facts.get('version')} · {facts.get('database')}", landscape=True)

    report.heading('How a statement runs')
    for stage in workshop.PIPELINE:
        report.paragraph(f"{stage['stage']} — {stage['what']}")

    report.heading('Joins')
    report.table(['Kind', 'Demonstration', 'What it answers'],
                 [[demo['label'], demo['title'], demo['question']]
                  for demo in workshop.join_demos()],
                 widths=[1.6, 3.4, 4.0])

    report.heading('Views')
    report.table(['View', 'Rows', 'What it hides'],
                 [[view['name'], str(view['rows']), (view['hides'] or view['purpose'])[:120]]
                  for view in workshop.views()],
                 widths=[2.6, 0.8, 5.6])

    report.heading('Stored procedures')
    report.table(['Procedure', 'Parameters', 'Guarantee'],
                 [[item['name'],
                   ', '.join(f"{param['mode']} {param['name']} {param['type']}"
                             for param in item['params']),
                   (item['guarantees'] or item['purpose'])[:150]]
                  for item in workshop.procedures()],
                 widths=[2.0, 2.6, 4.4])

    report.heading('Stored functions')
    report.table(['Function', 'Signature', 'Why it is a function'],
                 [[item['name'], item['signature'] or item['returns'],
                   (item['why'] or item['purpose'])[:150]] for item in workshop.functions()],
                 widths=[2.0, 2.8, 4.2])

    report.heading('Triggers and the rule each one enforces')
    report.table(['Trigger', 'On', 'Timing / event', 'Rule'],
                 [[item['name'], item['table'], f"{item['timing']} {item['event']}",
                   (item['rule'] or item['message'])[:150]] for item in workshop.triggers()],
                 widths=[2.4, 1.4, 1.6, 3.6])

    report.heading('Tables')
    report.table(['Table', 'Rows', 'Columns', 'Foreign keys'],
                 [[table['name'], str(table['rows']), str(len(table['columns'])),
                   str(len(table['foreign_keys']))] for table in workshop.schema()],
                 widths=[2.6, 1.0, 1.2, 1.6])

    report.paragraph('Every table above was read from the live catalogue at the moment this PDF '
                     'was generated; the triggers and views are the ones actually installed.')
    payload = report.to_bytes()
    return Response(payload, mimetype='application/pdf',
                    headers={'Content-Disposition': 'attachment; filename=nist_database_workshop.pdf'})
