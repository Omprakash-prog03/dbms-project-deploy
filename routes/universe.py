"""The Marvel & DC Universe module.

    /universe                  landing page: counts, comparisons, distribution
    /universe/characters       filterable character browser
    /universe/characters/<id>  character card
    /universe/teams            teams + roster drill-down
    /universe/powers           power catalogue with holder counts
    /universe/memberships      membership ledger
    /universe/screen           films and series
    /universe/comics           comic issues
    /universe/missions         storylines
    /universe/organizations    organisations and their leaders
    /universe/battles          battles + combatant roster
    /universe/relationships    relationship network
    /universe/sql              SQL demonstration gallery (read-only)
    /universe/verify           live verification and the generated reports
    /universe/datasets/<file>  the dataset files themselves

Visibility follows the portal's own rule: everyone signed in can read, because the
data is public fiction. The SQL gallery and the verification page are administrator
only, like every other SQL surface in this portal.
"""
import os

from flask import (Blueprint, abort, current_app, jsonify, render_template, request,
                   send_file)

from repositories import universe as repo
from routes.auth import login_required, role_required

universe_bp = Blueprint('universe', __name__, url_prefix='/universe')


@universe_bp.before_request
@login_required
def _signed_in():
    """Every page in this module needs a session, exactly like the rest of the portal."""
    return None


def _guard_missing():
    """The one place that turns a missing dataset into a friendly page."""
    if repo.installed():
        return None
    return render_template('universe/missing.html'), 200


@universe_bp.route('/')
def index():
    missing = _guard_missing()
    if missing:
        return missing
    data = repo.overview()
    return render_template('universe/index.html', **data,
                           counts=repo.counts())


@universe_bp.route('/characters')
def characters():
    missing = _guard_missing()
    if missing:
        return missing
    data = repo.character_page(request.args)
    return render_template('universe/characters.html', **data)


@universe_bp.route('/characters/<int:character_id>')
def character(character_id):
    missing = _guard_missing()
    if missing:
        return missing
    detail = repo.character_detail(character_id)
    if not detail:
        abort(404, description='No character with that id.')
    return render_template('universe/character.html', **detail)


@universe_bp.route('/teams')
def teams():
    missing = _guard_missing()
    if missing:
        return missing
    return render_template('universe/teams.html', **repo.teams_page(request.args))


@universe_bp.route('/teams/<int:team_id>')
def team(team_id):
    missing = _guard_missing()
    if missing:
        return missing
    detail = repo.team_detail(team_id)
    if not detail:
        abort(404, description='No team with that id.')
    return render_template('universe/team.html', **detail)


@universe_bp.route('/powers')
def powers():
    missing = _guard_missing()
    if missing:
        return missing
    return render_template('universe/powers.html', **repo.powers_page(request.args))


@universe_bp.route('/memberships')
def memberships():
    missing = _guard_missing()
    if missing:
        return missing
    return render_template('universe/memberships.html', **repo.membership_page(request.args))


@universe_bp.route('/screen')
def screen():
    missing = _guard_missing()
    if missing:
        return missing
    return render_template('universe/screen.html', **repo.screen_page(request.args))


@universe_bp.route('/comics')
def comics():
    missing = _guard_missing()
    if missing:
        return missing
    return render_template('universe/comics.html', **repo.comics_page(request.args))


@universe_bp.route('/missions')
def missions():
    missing = _guard_missing()
    if missing:
        return missing
    return render_template('universe/missions.html', **repo.missions_page(request.args))


@universe_bp.route('/missions/<int:mission_id>')
def mission(mission_id):
    missing = _guard_missing()
    if missing:
        return missing
    detail = repo.mission_detail(mission_id)
    if not detail:
        abort(404, description='No mission with that id.')
    return render_template('universe/mission.html', **detail)


@universe_bp.route('/organizations')
def organizations():
    missing = _guard_missing()
    if missing:
        return missing
    return render_template('universe/organizations.html',
                           **repo.organizations_page(request.args))


@universe_bp.route('/battles')
def battles():
    missing = _guard_missing()
    if missing:
        return missing
    return render_template('universe/battles.html', **repo.battles_page(request.args))


@universe_bp.route('/battles/<int:battle_id>')
def battle(battle_id):
    missing = _guard_missing()
    if missing:
        return missing
    detail = repo.battle_detail(battle_id)
    if not detail:
        abort(404, description='No battle with that id.')
    return render_template('universe/battle.html', **detail)


@universe_bp.route('/relationships')
def relationships():
    missing = _guard_missing()
    if missing:
        return missing
    return render_template('universe/relationships.html',
                           **repo.relationships_page(request.args))


@universe_bp.route('/sql')
@role_required('admin')
def sql_gallery():
    missing = _guard_missing()
    if missing:
        return missing
    try:
        index = int(request.args.get('q') or 0)
    except ValueError:
        index = 0
    index = max(0, min(index, len(repo.DEMO_QUERIES) - 1))
    result = repo.run_demo(index)
    return render_template('universe/sql.html', queries=repo.DEMO_QUERIES, index=index,
                           result=result)


@universe_bp.route('/compile', methods=['POST'])
@role_required('admin')
def compile_dataset():
    """Run the generator in-process: an administrator action, with a visible result."""
    from scripts import build_universe_dataset as builder
    try:
        entities, indexes = builder.build()
        report = builder.validate(entities, indexes)
        orphans = sum(len(f['orphans']) for f in report['foreign_keys'])
        if orphans:
            return jsonify(ok=False, message=f'Validation found {orphans} orphan rows; '
                                             'nothing was loaded.'), 400
        builder.write_csvs(entities)
        builder.write_sql(entities)
        builder.write_excel(entities)
        builder.write_data_dictionary(entities, report)
        builder.write_er_diagram(entities, report)
        builder.write_validation_report(entities, report, [], None)
        loaded, log, applied = builder.load(entities, reset=True)
        counts, fks, views = builder.verify(entities)
        builder.write_insertion_log(entities, loaded, log, applied, (counts, fks, views),
                                    fks, views, 'in-process rebuild triggered from the portal')
        total = sum(c['actual'] for c in counts.values())
        ok = all(c['ok'] for c in counts.values())
        return jsonify(ok=ok, message=(f'{total:,} rows rebuilt and verified across 14 tables.'
                                       if ok else 'Load finished but row counts differ.'),
                       counts={k: v['actual'] for k, v in counts.items()})
    except Exception as exc:  # reported, never swallowed
        current_app.logger.exception('Universe rebuild failed')
        return jsonify(ok=False, message=f'Rebuild failed: {exc}'), 500


@universe_bp.route('/verify')
@role_required('admin')
def verify():
    missing = _guard_missing()
    if missing:
        return missing
    return render_template('universe/verify.html', integrity=repo.integrity(),
                           counts=repo.counts(), artifacts=repo.artifacts(),
                           validation=repo.report_text('validation_report.md'),
                           insertion=repo.report_text('insertion_log.md'))


@universe_bp.route('/datasets/<path:name>')
@role_required('admin')
def download(name):
    path = repo.artifact_path(name)
    if not path:
        abort(404, description='No such dataset file.')
    return send_file(path, as_attachment=True, download_name=os.path.basename(name))
