"""Raw table browsing: the real rows, exactly as the database returns them.

Read-only. Administrator only. Credential and photo columns are never selected,
so they cannot leak through the screen, CSV or PDF.
"""
import re
from repositories.db_pool import db_pool
from repositories.pdf import CHAR_WIDTH, Report
from config import Config

HIDDEN_COLUMNS = {'password_hash', 'photo_url'}
DEFAULT_PAGE_SIZE = 20
PAGE_SIZES = (10, 20, 50, 100)
_SAFE_TABLE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


def _quote(identifier):
    if not _SAFE_TABLE.match(identifier):
        raise ValueError('Unknown table.')
    return identifier if db_pool.is_mysql else f'"{identifier}"'


def table_names():
    if db_pool.is_mysql:
        rows = db_pool.execute_query(
            "SELECT table_name AS name FROM information_schema.tables "
            "WHERE table_schema = DATABASE() AND table_type = 'BASE TABLE' ORDER BY table_name"
        )
    else:
        rows = db_pool.execute_query(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    return [row['name'] for row in rows if _SAFE_TABLE.match(row['name'])]


def row_count(name):
    return db_pool.execute_query(f'SELECT COUNT(*) FROM {_quote(name)}', fetch='val') or 0


def tables():
    """Every physical table with its row count, for the table picker."""
    return [{'name': name, 'rows': row_count(name)} for name in table_names()]


def columns(table, known=None):
    """Visible columns plus which ones are numeric (for right alignment)."""
    if table not in (known if known is not None else table_names()):
        raise ValueError('Unknown table.')
    if db_pool.is_mysql:
        rows = db_pool.execute_query(
            "SELECT column_name AS name, data_type AS type, column_key AS key_type "
            "FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name=%s "
            "ORDER BY ordinal_position", (table,), fetch='all')
        details = [{'name': row['name'], 'type': (row['type'] or '').lower(),
                    'primary': row['key_type'] == 'PRI'} for row in rows]
    else:
        rows = db_pool.execute_query(f'PRAGMA table_info({_quote(table)})')
        details = [{'name': row['name'], 'type': (row['type'] or '').lower(),
                    'primary': bool(row['pk'])} for row in rows]
    visible = []
    for column in details:
        if column['name'] in HIDDEN_COLUMNS:
            continue
        numeric = any(token in column['type'] for token in ('int', 'dec', 'num', 'real', 'float', 'double'))
        visible.append({**column, 'numeric': numeric})
    return visible


def _stable_widths(table, column_list):
    """One aggregate query so columns keep the same width on every page."""
    names = [column['name'] for column in column_list]
    if not names:
        return []
    projection = ', '.join(
        f'MAX(LENGTH({_quote(name)})) AS w{position}' for position, name in enumerate(names)
    )
    try:
        row = db_pool.execute_query(
            f'SELECT {projection} FROM {_quote(table)}', fetch='one') or {}
    except Exception:
        return None
    widths = []
    for position, column in enumerate(column_list):
        longest = row.get(f'w{position}') or 0
        widths.append(max(6, min(max(len(column['name']), int(longest)), 20)))
    return widths


def _order_clause(columns_):
    primary = [column['name'] for column in columns_ if column['primary']]
    chosen = primary or [columns_[0]['name']] if columns_ else []
    return ', '.join(_quote(name) for name in chosen)


def fetch(table, page=1, per_page=DEFAULT_PAGE_SIZE):
    """Return one page of raw rows plus everything needed to render them."""
    if table not in table_names():
        raise ValueError('Unknown table.')
    per_page = int(per_page) if int(per_page) in PAGE_SIZES else DEFAULT_PAGE_SIZE
    total = db_pool.execute_query(f'SELECT COUNT(*) FROM {_quote(table)}', fetch='val') or 0
    pages = max(1, (total + per_page - 1) // per_page)
    page = min(max(1, int(page or 1)), pages)
    offset = (page - 1) * per_page

    column_list = columns(table)
    names = [column['name'] for column in column_list]
    selected = ', '.join(_quote(name) for name in names)
    order = _order_clause(column_list)
    shown_columns = ', '.join(names)
    shown_order = ', '.join(column['name'] for column in column_list if column['primary']) or (
        names[0] if names else '')
    sql = (f'SELECT {selected} FROM {_quote(table)}'
           + (f' ORDER BY {order}' if order else '')
           + f' LIMIT {per_page} OFFSET {offset}')
    display_statement = (f'SELECT {shown_columns} FROM {table}'
                         + (f' ORDER BY {shown_order}' if shown_order else '')
                         + f' LIMIT {per_page} OFFSET {offset};')

    raw_rows = db_pool.execute_query(sql, fetch='all') if names else []
    rows = []
    for index, row in enumerate(raw_rows, start=offset + 1):
        rows.append({
            'number': index,
            'cells': ['' if row[name] is None else str(row[name]) for name in names],
        })

    # Column display widths: widest value, capped so one long address cannot
    # stretch the whole table beyond the page.
    widths = _stable_widths(table, column_list)
    if not widths:
        widths = []
        for position, column in enumerate(column_list):
            longest = max([len(column['name'])] + [len(row['cells'][position]) for row in rows] or [0])
            widths.append(max(6, min(longest, 20)))
    return {
        'table': table,
        'columns': column_list,
        'rows': rows,
        'widths': widths,
        'total': total,
        'page': page,
        'pages': pages,
        'per_page': per_page,
        'offset': offset,
        'statement': display_statement,
        'engine': 'MySQL 8' if db_pool.is_mysql else 'SQLite',
        'shown': len(rows),
    }


def display_cells(page_data):
    """Truncate cell text to the computed widths and right-align numbers."""
    output = []
    for row in page_data['rows']:
        cells = []
        for position, value in enumerate(row['cells']):
            width = page_data['widths'][position]
            text = value if len(value) <= width else value[: width - 1] + '…'
            numeric = page_data['columns'][position]['numeric']
            cells.append({'text': text, 'numeric': numeric, 'raw': value})
        output.append({'number': row['number'], 'cells': cells})
    return output


def grid_text(headers, numeric, widths, rows, numbers=None, empty_message='No rows in this table yet.'):
    """Oracle/SQL*Plus style block: header, dashed rule, aligned rows.

    Shared by the raw table viewer and the SQL console so both print results
    the same way.
    """
    def line(values, right=False):
        cells = []
        for position, value in enumerate(values):
            text = str(value)
            width = widths[position]
            cells.append(text.rjust(width) if (right or numeric[position]) else text.ljust(width))
        return '  '.join(cells).rstrip()

    if not rows:
        return empty_message
    lines = [line([str(header).upper() for header in headers]),
             line(['-' * width for width in widths]),
             '']
    for index, values in enumerate(rows):
        number = numbers[index] if numbers else index + 1
        lines.append(f'{str(number).rjust(4)}  ' + line(values))
    return '\n'.join(lines)


def render_text(page_data):
    """The current page of a raw table, ready for a <pre> block."""
    shown = display_cells(page_data)
    return grid_text(
        [column['name'] for column in page_data['columns']],
        [column['numeric'] for column in page_data['columns']],
        page_data['widths'],
        [[cell['text'] for cell in row['cells']] for row in shown],
        [row['number'] for row in shown],
    )


def table_csv(table):
    """Entire raw table as CSV text (credentials and photos excluded)."""
    if table not in table_names():
        raise ValueError('Unknown table.')
    column_list = columns(table)
    names = [column['name'] for column in column_list]
    statement = f'SELECT {", ".join(_quote(name) for name in names)} FROM {_quote(table)}'
    order = _order_clause(column_list)
    if order:
        statement += f' ORDER BY {order}'
    rows = db_pool.execute_query(statement, fetch='all') if names else []
    import csv
    import io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(names)
    for row in rows:
        writer.writerow([_safe_cell(row[name]) for name in names])
    return output.getvalue()


def _safe_cell(value):
    if value is None:
        return ''
    text = str(value)
    return "'" + text if text.lstrip().startswith(('=', '+', '-', '@', '\t', '\r')) else text


def table_pdf(table, limit=200):
    """Raw table as a landscape PDF, capped so the download stays small."""
    page_data = fetch(table, page=1, per_page=min(limit, 100))
    all_rows = []
    for page in range(1, page_data['pages'] + 1):
        if len(all_rows) >= limit:
            break
        chunk = fetch(table, page=page, per_page=page_data['per_page'])
        all_rows.extend([[cell['raw'] for cell in row['cells']] for row in display_cells(chunk)])

    report = Report(
        f'{Config.PORTAL_NAME} - Raw table: {table}',
        f'{page_data["engine"]} | {page_data["total"]:,} rows in total'
        + (f' | first {len(all_rows)} shown' if len(all_rows) < page_data['total'] else ''),
        landscape=True,
    )
    names = [column['name'] for column in page_data['columns']]
    order = ', '.join(column['name'] for column in page_data['columns'] if column['primary']) or (
        names[0] if names else '')
    report.heading('SQL')
    report.paragraph(
        f'SELECT {", ".join(names)} FROM {table}' + (f' ORDER BY {order}' if order else '') + ';'
    )

    headers = ['#'] + names
    table_rows = [[str(index)] + [str(value) for value in values]
                  for index, values in enumerate(all_rows, start=1)]
    # Width plan, in points: every column reserves its heading plus up to 14
    # characters, so short columns (gender, dates, phones) never truncate;
    # whatever is left over is shared by the genuinely long columns (email,
    # address). The 8pt gap the PDF renderer leaves between columns is part of
    # each column's reservation.
    char_width = 8.5 * CHAR_WIDTH
    samples = [max([len(str(row[position])) for row in all_rows] or [0])
               for position in range(len(page_data['columns']))]
    guaranteed = [max(len(column['name']), min(sample, 14))
                  for column, sample in zip(page_data['columns'], samples)]
    row_number_width = char_width * 3 + 8
    spent = row_number_width + sum(char_width * size + 8 for size in guaranteed)
    flexible = [position for position, sample in enumerate(samples) if sample > 14]
    spare = max(0, report.content_width - spent)
    widths = [row_number_width]
    for position, base in enumerate(guaranteed):
        extra = 0
        if position in flexible and flexible:
            extra = min(min(samples[position], 20), base + 8) - base
            extra = max(0, min(extra, spare / len(flexible) / char_width))
        widths.append(char_width * (base + extra) + 8)
    report.table(headers, table_rows, widths=widths,
                 align_right=tuple(index + 1 for index, column in enumerate(page_data['columns']) if column['numeric']))
    report.paragraph('Credentials (password_hash) and photo columns are excluded from every raw export. '
                     'Values are shown exactly as stored; NULL is printed as an empty cell.')
    return report.to_bytes()
