import pytest
from app import create_app

@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret"
    with app.test_client() as client:
        # Simulate logged in admin session
        with client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "admin"
            sess["role"] = "admin"
        yield client

def test_dashboard_route(client):
    res = client.get("/dashboard")
    assert res.status_code == 200
    assert b"Your campus." in res.data
    assert b"moduleGrid" in res.data
    assert b"A campus in motion" in res.data

def test_students_route(client):
    res = client.get("/students")
    assert res.status_code == 200
    assert b"Students Directory" in res.data

def test_student_profile_route(client):
    res = client.get("/students/1")
    assert res.status_code == 200
    assert b"Student 360" in res.data
    assert b"Cumulative CGPA" in res.data

def test_faculty_route(client):
    res = client.get("/faculty")
    assert res.status_code == 200
    assert b"Faculty Directory" in res.data

def test_departments_route(client):
    res = client.get("/departments")
    assert res.status_code == 200
    assert b"Academic Departments" in res.data

def test_courses_route(client):
    res = client.get("/courses")
    assert res.status_code == 200
    assert b"Course Catalog" in res.data

def test_offerings_route(client):
    res = client.get("/offerings")
    assert res.status_code == 200
    assert b"Active Course Offerings" in res.data

def test_enrollments_route(client):
    res = client.get("/enrollments")
    assert res.status_code == 200
    assert b"Enrollment Operations" in res.data

def test_attendance_route(client):
    res = client.get("/attendance")
    assert res.status_code == 200
    assert b"Class Roll-Call" in res.data

def test_results_route(client):
    res = client.get("/results")
    assert res.status_code == 200
    assert b"Gradebook" in res.data

def test_fees_route(client):
    res = client.get("/fees")
    assert res.status_code == 200
    assert b"Fee Accounting" in res.data

def test_insights_route(client):
    res = client.get("/insights")
    assert res.status_code == 200
    assert b"Database Insights" in res.data

def test_inspect_sql_endpoint(client):
    # Perform a query first
    client.get("/students")
    res = client.get("/api/inspect-sql")
    assert res.status_code == 200
    data = res.get_json()
    assert "queries" in data
    assert len(data["queries"]) > 0

def test_insights_query_execution_api(client):
    res = client.get("/api/insights/execute/Q01")
    assert res.status_code == 200
    data = res.get_json()
    assert "rows" in data
    assert len(data["rows"]) > 0

def test_insights_transaction_demo_api(client):
    res = client.post("/api/insights/transaction-demo")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["initial_count"] == data["final_count"]
