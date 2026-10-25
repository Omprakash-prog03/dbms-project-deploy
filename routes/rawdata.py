"""Administrator-only raw table browser and exports."""
from flask import Blueprint, Response, abort, render_template, request
from routes.auth import login_required, role_required
from repositories import rawdata

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
