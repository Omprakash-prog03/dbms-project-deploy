"""Administrator-only raw table browser and exports."""
from flask import Blueprint, Response, abort, render_template, request, session
from config import Config
from repositories.db_pool import db_pool
from routes.auth import login_required, role_required
from repositories import rawdata, sqlconsole

rawdata_bp = Blueprint('rawdata', __name__)


@rawdata_bp.route('/raw-data')
@login_required
@role_required('admin')
def raw_view():
    listing = rawdata.tables()
    names = [table['name'] for table in listing]
    requested = (request.args.get('table') or '').strip()
    table = requested if requested in names else (names[0] if names else None)
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', rawdata.DEFAULT_PAGE_SIZE, type=int)

    data = None
    if table:
        data = rawdata.fetch(table, page=page, per_page=per_page)
        data['display_rows'] = rawdata.display_cells(data)
        data['text'] = rawdata.render_text(data)
    return render_template('rawdata/index.html', tables=listing, data=data, table=table,
                           per_page=per_page, page_sizes=rawdata.PAGE_SIZES)


@rawdata_bp.route('/raw-data/query', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def query_console():
    """A real SQL prompt: read freely, change data, never change the schema."""
    statement = ''
    outcome = None
    allow_full_write = False
    if request.method == 'POST':
        statement = request.form.get('statement', '')
        allow_full_write = request.form.get('allow_full_write') == '1'
        outcome = sqlconsole.run(statement, allow_full_write=allow_full_write)
        sqlconsole.remember(session, outcome)
    return render_template(
        'rawdata/query.html',
        outcome=outcome,
        statement=statement,
        allow_full_write=allow_full_write,
        history=session.get('sql_history', []),
        examples=sqlconsole.examples(),
        schema=sqlconsole.schema_reference(),
        engine='MySQL 8' if db_pool.is_mysql else 'SQLite',
        database=Config.DB_NAME if db_pool.is_mysql else Config.SQLITE_PATH,
    )


@rawdata_bp.route('/raw-data/<table>.csv')
@login_required
@role_required('admin')
def raw_csv(table):
    try:
        payload = rawdata.table_csv(table)
    except ValueError:
        abort(404, description='Unknown table.')
    return Response(payload, mimetype='text/csv', headers={
        'Content-Disposition': f'attachment; filename=nist-raw-{table}.csv',
        'Cache-Control': 'no-store',
    })


@rawdata_bp.route('/raw-data/<table>.pdf')
@login_required
@role_required('admin')
def raw_pdf(table):
    try:
        payload = rawdata.table_pdf(table)
    except ValueError:
        abort(404, description='Unknown table.')
    return Response(payload, mimetype='application/pdf', headers={
        'Content-Disposition': f'attachment; filename=nist-raw-{table}.pdf',
        'Cache-Control': 'no-store',
    })
