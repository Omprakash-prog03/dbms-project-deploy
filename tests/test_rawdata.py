"""Raw table browser: Oracle-style output plus CSV and PDF exports."""
import pytest
from app import create_app
from config import Config
from repositories import rawdata


@pytest.fixture
def admin():
    client = create_app({'TESTING': True, 'CSRF_ENABLED': False, 'RATELIMIT_ENABLED': False}).test_client()
    with client.session_transaction() as session:
        session.update(user_id=1, username='admin', role='admin')
    return client


@pytest.fixture
def faculty():
    client = create_app({'TESTING': True, 'CSRF_ENABLED': False}).test_client()
    with client.session_transaction() as session:
        session.update(user_id=2, username='faculty', role='faculty', faculty_id=1)
    return client


@pytest.fixture
def student():
    client = create_app({'TESTING': True, 'CSRF_ENABLED': False}).test_client()
    with client.session_transaction() as session:
        session.update(user_id=3, username='student', role='student', student_id=1)
    return client


def test_administrator_sees_raw_table_page(admin):
    page = admin.get('/raw-data')
    assert page.status_code == 200
    body = page.data
    assert b'raw-output' in body
    assert b'SELECT ' in body and b'LIMIT 20 OFFSET 0;' in body
    assert b'SQL&gt;' in body
    # The statement is shown the way a person would type it, without identifiers quoted.
    student_page = admin.get('/raw-data?table=student')
    assert b'FROM student' in student_page.data
    assert b'&quot;student&quot;' not in student_page.data
    # Credentials never reach the page.
    assert b'$2b$' not in body


def test_each_table_can_be_opened(admin):
    for name in rawdata.table_names():
        response = admin.get(f'/raw-data?table={name}')
        assert response.status_code == 200, name
    listing = admin.get('/raw-data?table=app_user')
    assert b'password_hash' not in listing.data or b'not listed' in listing.data
    assert b'$2b$' not in listing.data


def test_non_administrators_are_refused(faculty, student):
    for client in (faculty, student):
        assert client.get('/raw-data').status_code == 403
        assert client.get('/raw-data/student.csv').status_code == 403
        assert client.get('/raw-data/student.pdf').status_code == 403


def test_anonymous_is_sent_to_login():
    client = create_app({'TESTING': True, 'CSRF_ENABLED': False}).test_client()
    response = client.get('/raw-data')
    assert response.status_code in (302, 401)


def test_password_hash_is_never_a_visible_column():
    visible = [column['name'] for column in rawdata.columns('app_user')]
    assert 'password_hash' not in visible
    assert 'photo_url' not in visible
    assert visible

    page = rawdata.fetch('app_user')
    assert page['columns']
    assert all(column['name'] not in rawdata.HIDDEN_COLUMNS for column in page['columns'])
    assert 'password_hash' not in page['statement']
    assert 'photo_url' not in page['statement']


def test_pagination_is_clamped_and_page_sizes_restricted(admin):
    first = rawdata.fetch('student', page=1, per_page=10)
    assert first['per_page'] == 10
    assert first['shown'] <= 10

    far = rawdata.fetch('student', page=999, per_page=10)
    assert far['page'] == far['pages']
    assert far['offset'] == (far['pages'] - 1) * 10

    weird = rawdata.fetch('student', page=1, per_page=7)
    assert weird['per_page'] == rawdata.DEFAULT_PAGE_SIZE

    negative = rawdata.fetch('student', page=-4, per_page=10)
    assert negative['page'] == 1

    assert admin.get('/raw-data?table=student&page=999').status_code == 200


def test_alignment_and_widths_are_consistent_across_pages():
    page_one = rawdata.fetch('student', page=1, per_page=10)
    page_two = rawdata.fetch('student', page=2, per_page=10)
    assert page_one['widths'] == page_two['widths']
    assert sum(1 for column in page_one['columns'] if column['numeric']) >= 1

    text = rawdata.render_text(page_one)
    header, rule = text.splitlines()[0], text.splitlines()[1]
    assert 'ID' in header
    assert set(rule.replace(' ', '')) == {'-'}


def test_unknown_tables_are_rejected(admin):
    assert admin.get('/raw-data/not_a_table.csv').status_code == 404
    assert admin.get('/raw-data/not_a_table.pdf').status_code == 404
    with pytest.raises(ValueError):
        rawdata.fetch('not_a_table')
    with pytest.raises(ValueError):
        rawdata.table_csv('student; DROP TABLE student')
    assert rawdata.fetch('student')['total'] >= 1


def test_csv_export_matches_the_table(admin):
    response = admin.get('/raw-data/student.csv')
    assert response.status_code == 200
    assert response.mimetype == 'text/csv'
    assert 'attachment' in response.headers['Content-Disposition']
    assert 'nist-raw-student.csv' in response.headers['Content-Disposition']
    lines = response.get_data(as_text=True).splitlines()
    assert lines[0].startswith('student_id,roll_no,first_name')
    assert len(lines) - 1 == rawdata.fetch('student', per_page=100)['total']

    users = admin.get('/raw-data/app_user.csv').get_data(as_text=True)
    assert 'password_hash' not in users
    assert '$2b$' not in users


def test_pdf_export_is_a_landscape_document(admin):
    response = admin.get('/raw-data/student.pdf')
    assert response.status_code == 200
    assert response.mimetype == 'application/pdf'
    payload = response.data
    assert payload.startswith(b'%PDF-1.4') and b'%%EOF' in payload[-16:]
    # Landscape A4 media box.
    assert b'842' in payload and b'595' in payload
    users = admin.get('/raw-data/app_user.pdf')
    assert users.status_code == 200
    assert b'$2b$' not in users.data

    # The statement is printed unquoted, and narrow columns are not truncated.
    assert b'FROM student' in payload and b'\"student\"' not in payload
    assert b'9876500001' in payload and b'2005-04-12' in payload
    department = admin.get('/raw-data/department.pdf')
    assert b'Computer Science &' in department.data
    assert b'Information Technology' in department.data


def test_csv_escapes_formula_characters():
    assert rawdata._safe_cell('=1+1').startswith("'=")
    assert rawdata._safe_cell(None) == ''
    assert rawdata._safe_cell('plain') == 'plain'


def test_navigation_links_to_raw_data_only_for_administrators(admin, faculty):
    assert b'/raw-data' in admin.get('/reports').data
    assert b'/raw-data' not in faculty.get('/reports').data


def test_other_pages_are_untouched(admin):
    for path in ('/dashboard', '/reports', '/insights', '/students'):
        assert admin.get(path).status_code in (200, 302), path
    assert Config.PORTAL_NAME
