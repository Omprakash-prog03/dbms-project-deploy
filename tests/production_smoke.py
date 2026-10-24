"""Executed in a subprocess against a disposable private installation, not the preview."""
import datetime
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wsgi import application
from repositories.db_pool import db_pool

credentials = json.loads(sys.stdin.read())
base = 'https://localhost'
client = application.test_client()
assert client.get('/healthz', base_url=base).status_code == 200
assert client.get('/dashboard', base_url=base).status_code == 302
login = client.get('/login', base_url=base)
assert b'NIST University Portal Management' in login.data
assert b'data-demo=' not in login.data
assert login.headers['X-Frame-Options'] == 'SAMEORIGIN'
assert "frame-ancestors 'self'" in login.headers['Content-Security-Policy']
assert 'max-age=' in login.headers['Strict-Transport-Security']
with client.session_transaction(base_url=base) as session:
    token = session['csrf_token']
assert client.post('/api/auth/login', json=credentials, base_url=base).status_code == 400
response = client.post('/api/auth/login', json=credentials, headers={'X-CSRF-Token':token}, base_url=base)
assert response.status_code == 200, response.get_json()
with client.session_transaction(base_url=base) as session:
    token = session['csrf_token']
assert b'Set up your first department' in client.get('/dashboard', base_url=base).data
for table in ('department', 'faculty', 'student', 'admission_application', 'course', 'fee_payment'):
    assert db_pool.execute_query(f'SELECT COUNT(*) FROM {table}', fetch='val') == 0


def post(path, payload):
    response = client.post(path, json=payload, headers={'X-CSRF-Token':token}, base_url=base)
    assert response.status_code == 200, (path, response.get_json())
    return response.get_json()


department = post('/api/departments/create', {'dept_code':'CSE','dept_name':'Computer Science','established_year':2020})['dept_id']
faculty = post('/api/faculty/create', {'first_name':'Casey','last_name':'Tutor','email':'instructor@example.com','phone':'9876543210','dept_id':department,'designation':'Lecturer','salary':50000,'hire_date':'2020-01-01','initial_password':'Testing-only-faculty-42!','status':'Active'})['faculty_id']
post(f'/api/departments/update/{department}', {'dept_code':'CSE','dept_name':'Computer Science','established_year':2020,'hod_faculty_id':faculty})
course = post('/api/courses/create', {'course_code':'CSE101','title':'Computing Fundamentals','credits':3,'dept_id':department,'semester_no':1})['course_id']
year = datetime.date.today().year
offering = post('/api/offerings/create', {'course_id':course,'faculty_id':faculty,'academic_year':f'{year}-{year+1}','term':'Fall','capacity':20})['offering_id']
applicant = post('/api/admissions/create', {'applicant_name':'Casey Learner','email':'learner@example.com','phone':'9876543210','dept_id':department})['application_id']
approved = post('/api/admissions/approve', {'application_id':applicant,'dob':'2004-01-01','address':'Test-only address'})
student_id = db_pool.execute_query('SELECT student_id FROM app_user WHERE username=%s',(approved['username'],),fetch='val')
post('/api/enrollments/enroll', {'student_id':student_id,'offering_id':offering})
enrollment = db_pool.execute_query('SELECT enrollment_id FROM enrollment WHERE student_id=%s',(student_id,),fetch='val')
post('/api/attendance/mark', {'offering_id':offering,'class_date':datetime.date.today().isoformat(),'records':[{'enrollment_id':enrollment,'status':'Present'}]})
exam = post('/api/exams/create', {'offering_id':offering,'exam_type':'Internal','max_marks':'100','exam_date':datetime.date.today().isoformat()})['exam_id']
post('/api/results/save', {'exam_id':exam,'enrollment_id':enrollment,'marks_obtained':91})
post('/api/fees/structure/save', {'dept_id':department,'semester_no':1,'amount':'1000'})
post('/api/fees/pay', {'student_id':student_id,'semester_no':1,'amount':'100.25','mode':'Cash','receipt_no':'PRODUCTION-SMOKE-ONLY'})
for path in ('/dashboard','/students',f'/students/{student_id}','/faculty','/departments','/courses','/offerings','/enrollments','/attendance','/results','/fees','/admissions','/insights','/reports'):
    response = client.get(path, base_url=base)
    assert response.status_code == 200, path
    assert b'NIST University Portal Management' in response.data, path
for path, prefix in (('/reports/summary.pdf', b'%PDF-'), ('/students/%s/report.pdf' % student_id, b'%PDF-')):
    payload = client.get(path, base_url=base)
    assert payload.status_code == 200 and payload.data.startswith(prefix), path
assert b'password_hash' not in client.get('/reports/tables/app_user.csv', base_url=base).data
assert client.get('/api/dashboard/export-students',base_url=base).headers['Content-Disposition'].endswith('hogwards_students_export.csv')
assert client.post('/logout',data={'csrf_token':token},base_url=base).status_code == 302
assert client.get('/api/dashboard/stats',base_url=base).status_code == 401
client.get('/login',base_url=base)
with client.session_transaction(base_url=base) as session:
    student_token = session['csrf_token']
response = client.post('/api/auth/login',json={'username':approved['username'],'password':approved['temporary_password']},headers={'X-CSRF-Token':student_token},base_url=base)
assert response.status_code == 200
assert client.get(f'/students/{student_id}',base_url=base).status_code == 200
assert client.get('/students',base_url=base).status_code == 403
assert client.get('/fees',base_url=base).status_code == 403
print('PASS: empty private install → department → faculty → course → offering → admission → student account → enrollment → attendance → examination → result → payment → student-only access.')
