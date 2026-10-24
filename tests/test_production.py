"""Branding, private deployment, and newly unblocked empty-database workflows."""
from contextlib import closing
from datetime import date
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import subprocess
import sys
import uuid
import bcrypt
import pytest
from app import create_app
from repositories.db_pool import db_pool

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def admin():
    client = create_app({'TESTING':True,'CSRF_ENABLED':False,'RATELIMIT_ENABLED':False}).test_client()
    with client.session_transaction() as session:
        session.update(user_id=1,username='admin',role='admin')
    return client


@pytest.mark.parametrize('path',['/dashboard','/students','/students/1','/faculty','/departments','/courses','/offerings','/enrollments','/attendance','/results','/fees','/admissions','/insights'])
def test_hogwards_brand_is_on_every_page(admin,path):
    response = admin.get(path)
    assert response.status_code == 200
    title = re.search(rb'<title>(.*?)</title>',response.data).group(1)
    assert b'NIST University Portal Management' in title
    assert b'SIMS' not in title
    assert b'aria-label="NIST University Portal Management home"' in response.data


def test_public_branding_and_cookie_free_health():
    client = create_app({'TESTING':True}).test_client()
    for path in ('/login','/not-a-real-page'):
        assert b'NIST University Portal Management' in client.get(path).data
    response = create_app({'TESTING':True}).test_client().get('/healthz')
    assert response.status_code == 200
    assert response.get_json()['application'] == 'NIST University Portal Management'
    assert 'Set-Cookie' not in response.headers


def test_export_is_renamed_but_all_status_filter_is_preserved(admin):
    assert b'All statuses' in admin.get('/students?status=All').data
    assert 'hogwards_students_export.csv' in admin.get('/api/dashboard/export-students?status=All').headers['Content-Disposition']


def test_department_create_edit_and_validation(admin):
    code = 'Q'+uuid.uuid4().hex[:7].upper()
    created = admin.post('/api/departments/create',json={'dept_code':code,'dept_name':'Department '+code,'established_year':2020})
    assert created.status_code == 200, created.get_json()
    key = created.get_json()['dept_id']
    try:
        assert admin.post('/api/departments/create',json={'dept_code':code,'dept_name':'Duplicate','established_year':2020}).status_code == 400
        assert admin.post(f'/api/departments/update/{key}',json={'dept_code':code,'dept_name':'Updated '+code,'established_year':2021}).status_code == 200
        row = db_pool.execute_query('SELECT * FROM department WHERE dept_id=%s',(key,),fetch='one')
        assert row['dept_name'] == 'Updated '+code
        assert row['established_year'] == 2021
        assert admin.post(f'/api/departments/update/{key}',json={'dept_code':code,'dept_name':'Updated '+code,'established_year':2021,'hod_faculty_id':1}).status_code == 400
        assert admin.post(f'/api/departments/update/{key}',json={'dept_code':code,'dept_name':'Updated '+code,'established_year':date.today().year+1}).status_code == 400
    finally:
        db_pool.execute_dml('DELETE FROM department WHERE dept_id=%s',(key,))


@pytest.mark.parametrize('role',['faculty','student'])
def test_non_admin_cannot_create_departments(role):
    client = create_app({'TESTING':True,'CSRF_ENABLED':False}).test_client()
    with client.session_transaction() as session:
        session.update(user_id=2,username=role,role=role)
    assert client.post('/api/departments/create',json={}).status_code == 403


def test_application_creation_is_available_without_demo_seed(admin):
    email = uuid.uuid4().hex+'@example.com'
    payload = {'applicant_name':'New Private Applicant','email':email,'phone':'9876543210','dept_id':1}
    created = admin.post('/api/admissions/create',json=payload)
    assert created.status_code == 200, created.get_json()
    try:
        assert admin.post('/api/admissions/create',json=payload).status_code == 400
        assert admin.post('/api/admissions/create',json={**payload,'email':'bad-email'}).status_code == 400
    finally:
        db_pool.execute_dml('DELETE FROM admission_application WHERE application_id=%s',(created.get_json()['application_id'],))


def test_examination_validation_and_student_access(admin):
    offering = db_pool.execute_query('SELECT offering_id FROM course_offering LIMIT 1',fetch='val')
    payload = {'offering_id':offering,'exam_type':'Internal','max_marks':'NaN','exam_date':'2026-10-01'}
    assert admin.post('/api/exams/create',json=payload).status_code == 400
    client = create_app({'TESTING':True,'CSRF_ENABLED':False}).test_client()
    with client.session_transaction() as session:
        session.update(user_id=3,username='student',role='student',student_id=1)
    assert client.post('/api/exams/create',json=payload).status_code == 403
    assert client.post('/api/admissions/create',json={}).status_code == 403


def test_login_rate_limit_returns_429():
    app = create_app({'TESTING':True,'CSRF_ENABLED':False,'RATELIMIT_ENABLED':True})
    client = app.test_client()
    for _ in range(10):
        assert client.post('/api/auth/login',json={'username':'nonexistent-rate-test','password':'invalid'}).status_code == 401
    response = client.post('/api/auth/login',json={'username':'nonexistent-rate-test','password':'invalid'})
    assert response.status_code == 429
    assert 'Too many' in response.get_json()['message']
    assert int(response.headers['Retry-After']) > 0


@pytest.mark.parametrize('overrides',[
    {'SECRET_KEY':None}, {'SECRET_KEY':'short'}, {'DEMO_MODE':True},
    {'CSRF_ENABLED':False}, {'SESSION_COOKIE_SECURE':False}, {'DB_ENGINE':'auto'},
])
def test_production_rejects_unsafe_configuration(overrides):
    safe = {'APP_ENV':'production','SECRET_KEY':'x'*40,'DEMO_MODE':False,'CSRF_ENABLED':True,'SESSION_COOKIE_SECURE':True,'DB_ENGINE':'sqlite','RATELIMIT_ENABLED':False}
    with pytest.raises(RuntimeError):
        create_app({**safe,**overrides})


def test_private_initializer_and_complete_fresh_installation(tmp_path):
    configuration, database = tmp_path/'.env', tmp_path/'private.db'
    password = 'Test-only-'+secrets.token_urlsafe(16)
    payload = {'username':'headmaster','password':password,'config_path':str(configuration),'database_path':str(database)}
    code = 'import json,sys; from scripts.init_production import initialize; initialize(**json.loads(sys.stdin.read()))'
    result = subprocess.run([sys.executable,'-c',code],input=json.dumps(payload),capture_output=True,text=True,cwd=ROOT)
    assert result.returncode == 0, result.stderr
    assert password not in result.stdout + result.stderr + configuration.read_text()
    assert configuration.stat().st_mode & 0o777 == 0o600
    assert database.stat().st_mode & 0o777 == 0o600
    with closing(sqlite3.connect(database)) as connection:
        users = connection.execute('SELECT username,password_hash,role FROM app_user').fetchall()
        assert len(users) == 1 and users[0][0] == 'headmaster' and users[0][2] == 'admin'
        assert bcrypt.checkpw(password.encode(),users[0][1].encode())
        assert connection.execute('SELECT COUNT(*) FROM student').fetchone()[0] == 0
        assert connection.execute('SELECT COUNT(*) FROM department').fetchone()[0] == 0
    before = configuration.read_bytes()
    repeated = subprocess.run([sys.executable,'-c',code],input=json.dumps(payload),capture_output=True,text=True,cwd=ROOT)
    assert repeated.returncode != 0
    assert 'Refusing to overwrite' in repeated.stderr
    assert configuration.read_bytes() == before
    environment = os.environ.copy()
    for key in ('APP_ENV','SECRET_KEY','DB_ENGINE','SQLITE_PATH','DEMO_MODE','COOKIE_SECURE','EMBEDDED_PREVIEW','TRUSTED_PROXY_HOPS'):
        environment.pop(key,None)
    environment['HOGWARDS_ENV_FILE'] = str(configuration)
    check = subprocess.run([sys.executable,'scripts/check_production.py'],env=environment,capture_output=True,text=True,cwd=ROOT)
    assert check.returncode == 0, check.stdout+check.stderr
    refused_seed = subprocess.run([sys.executable,'-c','from db.seed import run_seed; run_seed()'],env=environment,capture_output=True,text=True,cwd=ROOT)
    assert refused_seed.returncode != 0
    assert 'Demo seeding is disabled in production' in refused_seed.stderr
    smoke = subprocess.run([sys.executable,'tests/production_smoke.py'],input=json.dumps({'username':'headmaster','password':password}),env=environment,capture_output=True,text=True,cwd=ROOT)
    assert smoke.returncode == 0, smoke.stdout+smoke.stderr
    assert 'PASS: empty private install' in smoke.stdout


def test_console_password_reset_random_and_check(tmp_path):
    """The printed one-time password must actually work at the web login."""
    configuration, database = tmp_path/'.env', tmp_path/'reset.db'
    password = 'Initial-Private-Pass-2026!'
    setup = subprocess.run(
        [sys.executable,'-c','import json,sys; from scripts.init_production import initialize; initialize(**json.loads(sys.stdin.read()))'],
        input=json.dumps({'username':'omprakash','password':password,'config_path':str(configuration),'database_path':str(database)}),
        capture_output=True,text=True,cwd=ROOT,
    )
    assert setup.returncode == 0, setup.stderr
    environment = {key: value for key, value in os.environ.items()
                   if key not in {'APP_ENV','SECRET_KEY','DB_ENGINE','SQLITE_PATH','DEMO_MODE','COOKIE_SECURE','EMBEDDED_PREVIEW','TRUSTED_PROXY_HOPS'}}
    environment['HOGWARDS_ENV_FILE'] = str(configuration)

    reset = subprocess.run([sys.executable,'scripts/reset_password.py','--random'],input='omprakash\n',
                           capture_output=True,text=True,cwd=ROOT,env=environment)
    assert reset.returncode == 0, reset.stderr
    assert str(database) in reset.stdout
    assert 'Verified against the database: OK' in reset.stdout
    generated = re.search(r'Generated password: (\S+)', reset.stdout).group(1)
    assert len(generated) >= 12
    assert generated not in configuration.read_text()

    check = subprocess.run([sys.executable,'scripts/reset_password.py','--check'],
                           input=f'omprakash\n{generated}\n',capture_output=True,text=True,cwd=ROOT,env=environment)
    assert 'MATCH - these credentials work' in check.stdout
    wrong = subprocess.run([sys.executable,'scripts/reset_password.py','--check'],
                           input='omprakash\ndefinitely-wrong-password\n',capture_output=True,text=True,cwd=ROOT,env=environment)
    assert 'NO MATCH' in wrong.stdout

    smoke = subprocess.run([sys.executable,'tests/production_smoke.py'],
                           input=json.dumps({'username':'omprakash','password':generated}),
                           capture_output=True,text=True,cwd=ROOT,env=environment)
    assert smoke.returncode == 0, smoke.stdout + smoke.stderr
    unknown = subprocess.run([sys.executable,'scripts/reset_password.py','--check'],
                             input='nobody-here\nwhatever\n',capture_output=True,text=True,cwd=ROOT,env=environment)
    assert unknown.returncode != 0
