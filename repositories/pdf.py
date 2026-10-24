"""Small, dependency-free PDF report builder (A4 portrait, built-in Helvetica).

Only text and simple tables are produced, so the free host needs no native PDF
library. Text is encoded as Latin-1; unsupported characters become '?'.
"""
from datetime import date

PAGE_WIDTH, PAGE_HEIGHT = 595, 842
MARGIN_X, TOP, BOTTOM = 50, 800, 64
CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN_X
CHAR_WIDTH = 0.5  # Helvetica average advance width, as a fraction of font size


def _escape(text):
    return (str(text).replace('\\', r'\\').replace('(', r'\(').replace(')', r'\)')
            .replace('\r', ' ').replace('\n', ' '))


def _clean(text):
    return str(text if text is not None else '').encode('latin-1', 'replace').decode('latin-1')


def _fit(text, width, size):
    """Truncate text to the available column width, in characters."""
    limit = max(3, int(width / (size * CHAR_WIDTH)))
    text = _clean(text)
    return text if len(text) <= limit else text[: limit - 3].rstrip() + '...'


def _money(value):
    try:
        return f'{float(value):,.2f}'
    except (TypeError, ValueError):
        return '-'


class Report:
    def __init__(self, title, subtitle=''):
        self.title = title
        self.subtitle = subtitle
        self.pages = []
        self._new_page()

    # ---- layout primitives -------------------------------------------------
    def _new_page(self):
        self.commands = []
        self.pages.append(self.commands)
        self.y = TOP
        self._page_header()

    def _page_header(self):
        self._text(MARGIN_X, TOP, _fit(self.title, CONTENT_WIDTH, 15), 15, bold=True)
        if self.subtitle:
            self._text(MARGIN_X, TOP - 18, _fit(self.subtitle, CONTENT_WIDTH, 9), 9, gray=True)
        self._rule(TOP - 30)
        self.y = TOP - 48

    def _text(self, x, y, text, size=10, bold=False, gray=False):
        red, green, blue = (0.42, 0.42, 0.47) if gray else (0.12, 0.12, 0.14)
        self.commands.append(('text', x, y, size, _escape(_clean(text)), bold, red, green, blue))

    def _rule(self, y, thickness=0.6, light=False):
        color = (0.85, 0.85, 0.88) if light else (0.72, 0.68, 0.88)
        self.commands.append(('rect', MARGIN_X, y, CONTENT_WIDTH, thickness, *color))

    def _need(self, height):
        """Start a new page if a block of `height` points would cross the margin."""
        if self.y - height < BOTTOM:
            self._new_page()
            return True
        return False

    def heading(self, text):
        if self._need(64):
            pass
        self.y -= 22
        self._text(MARGIN_X, self.y, _fit(text, CONTENT_WIDTH, 12), 12, bold=True)
        self._rule(self.y - 6, light=True)
        self.y -= 22

    def paragraph(self, text, size=9.5):
        limit = max(10, int(CONTENT_WIDTH / (size * CHAR_WIDTH)))
        words, line, lines = str(text).split(), '', []
        for word in words:
            candidate = f'{line} {word}'.strip()
            if len(candidate) > limit and line:
                lines.append(line)
                line = word
            else:
                line = candidate
        if line:
            lines.append(line)
        for entry in lines:
            self._need(14)
            self.y -= 13
            self._text(MARGIN_X, self.y, entry, size, gray=True)
        self.y -= 2

    def key_values(self, pairs, columns=2, row_height=30):
        pairs = [(str(key), str(value)) for key, value in pairs]
        column_width = CONTENT_WIDTH / max(1, columns)
        for index in range(0, len(pairs), columns):
            self._need(row_height)
            for offset, (label, value) in enumerate(pairs[index:index + columns]):
                x = MARGIN_X + offset * column_width
                self._text(x, self.y, _fit(label.upper(), column_width - 10, 7), 7, gray=True)
                self._text(x, self.y - 12, _fit(value, column_width - 10, 10), 10, bold=True)
            self.y -= row_height

    def _column_layout(self, widths):
        total = sum(widths) or 1
        return [CONTENT_WIDTH * width / total for width in widths]

    def _table_row(self, cells, column_widths, size, bold=False, align_right=(), gray=False):
        x = MARGIN_X
        for index, cell in enumerate(cells):
            text = _fit(cell, column_widths[index] - 8, size)
            if index in align_right:
                x_text = x + column_widths[index] - 8 - len(text) * size * CHAR_WIDTH
                self._text(x_text, self.y, text, size, bold=bold, gray=gray)
            else:
                self._text(x, self.y, text, size, bold=bold, gray=gray)
            x += column_widths[index]

    def table(self, headers, rows, widths=None, align_right=(), money_columns=()):
        widths = widths or [1] * len(headers)
        column_widths = self._column_layout(widths)
        size, row_height = 8.5, 16

        def header():
            self._need(row_height * 2)
            self._table_row(headers, column_widths, 7, bold=True, gray=True)
            self.y -= 5
            self._rule(self.y, light=True)
            self.y -= 3

        self.y -= 8
        header()
        rows = list(rows)
        if not rows:
            self._need(row_height)
            self.y -= row_height
            self._text(MARGIN_X, self.y, 'No records yet.', size, gray=True)
            self.y -= 6
            return
        for row in rows:
            if self._need(row_height):
                header()
            cells = []
            for index, cell in enumerate(row):
                cells.append(_money(cell) if index in money_columns else (cell if cell is not None else '-'))
            self.y -= row_height
            self._table_row([str(cell) for cell in cells], column_widths, size, align_right=align_right)
        self.y -= 6

    # ---- output ------------------------------------------------------------
    def to_bytes(self):
        # Page numbers are added after pagination, so they cannot affect layout.
        for number, commands in enumerate(self.pages, start=1):
            commands.append(('text', PAGE_WIDTH - MARGIN_X - 78, 34, 8,
                             _escape(f'NIST University | Page {number} of {len(self.pages)}'),
                             False, 0.55, 0.55, 0.60))

        objects = []

        def add(content):
            objects.append(content)
            return len(objects)

        font_regular = add(b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>')
        font_bold = add(b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>')
        pages_object_id = len(objects) + 1 + 2 * len(self.pages)
        page_ids = []
        for commands in self.pages:
            stream = '\n'.join(self._render(commands)).encode('latin-1')
            content_id = add(b'<< /Length %d >>\nstream\n' % len(stream) + stream + b'\nendstream')
            page_ids.append(add(
                ('<< /Type /Page /Parent %d 0 R /MediaBox [0 0 %d %d] '
                 '/Resources << /Font << /F1 %d 0 R /F2 %d 0 R >> >> /Contents %d 0 R >>'
                 % (pages_object_id, PAGE_WIDTH, PAGE_HEIGHT, font_regular, font_bold, content_id)).encode()
            ))
        kids = ' '.join(f'{pid} 0 R' for pid in page_ids)
        pages_id = add(('<< /Type /Pages /Kids [%s] /Count %d >>' % (kids, len(page_ids))).encode())
        assert pages_id == pages_object_id
        catalog_id = add(('<< /Type /Catalog /Pages %d 0 R >>' % pages_id).encode())
        info_id = add(('<< /Title (%s) /Producer (University Portal Management) >>' % _escape(self.title)).encode())

        output = bytearray(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')
        offsets = [0]
        for number, body in enumerate(objects, start=1):
            offsets.append(len(output))
            output += b'%d 0 obj\n' % number + body + b'\nendobj\n'
        xref = len(output)
        output += b'xref\n0 %d\n' % (len(objects) + 1)
        output += b'0000000000 65535 f \n'
        for offset in offsets[1:]:
            output += b'%010d 00000 n \n' % offset
        output += (b'trailer\n<< /Size %d /Root %d 0 R /Info %d 0 R >>\nstartxref\n%d\n%%%%EOF\n'
                   % (len(objects) + 1, catalog_id, info_id, xref))
        return bytes(output)

    @staticmethod
    def _render(commands):
        for command in commands:
            if command[0] == 'text':
                _, x, y, size, text, bold, red, green, blue = command
                font = 'F2' if bold else 'F1'
                yield (f'BT /{font} {size} Tf {red} {green} {blue} rg '
                       f'1 0 0 1 {x:.2f} {y:.2f} Tm ({text}) Tj ET')
            elif command[0] == 'rect':
                _, x, y, width, height, red, green, blue = command
                yield f'{red} {green} {blue} rg {x:.2f} {y:.2f} {width:.2f} {height:.2f} re f'
