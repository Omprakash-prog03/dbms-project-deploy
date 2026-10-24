import io
import csv
from datetime import date
from repositories.db_pool import db_pool
from flask import Blueprint, render_template, request, jsonify, Response, redirect, url_for, session
from routes.auth import login_required, role_required
from repositories.dashboard import DashboardRepository
from repositories.students import StudentRepository
from repositories.admissions import AdmissionsRepository
from repositories.faculty import FacultyRepository

dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.route("/")
def index():
    if "user_id" not in session:
        return redirect(url_for("auth.login_view"))
    return redirect(url_for("dashboard.dashboard_view"))

@dashboard_bp.route("/dashboard")
@login_required
def dashboard_view():
    if session.get("role") == "student":
        return redirect(url_for("students.profile_view", student_id=session["student_id"]))
    stats = DashboardRepository.get_stats()
    pending_apps = AdmissionsRepository.get_pending()
    students_data = StudentRepository.get_all(page=1, per_page=4, sort_col="admission_date", sort_dir="desc")
    departments = FacultyRepository.get_departments()

    return render_template(
        "dashboard.html",
        stats=stats,
        pending_apps=pending_apps[:4],
        chart_years=DashboardRepository.get_chart_years(),
        selected_year=date.today().year,
        students=students_data["items"],
        total_students=students_data["total"],
        departments=departments,
        current_page=1,
        total_pages=students_data["pages"]
    )

@dashboard_bp.route("/api/dashboard/stats")
@login_required
@role_required("admin", "faculty")
def api_stats():
    stats = DashboardRepository.get_stats()
    if session.get("role") != "admin":
        stats.pop("total_collected", None)
        stats.pop("payment_count", None)
    return jsonify(stats)

@dashboard_bp.route("/api/dashboard/chart")
@login_required
@role_required("admin", "faculty")
def api_chart():
    year = request.args.get("year", date.today().year, type=int)
    if not 1900 <= year <= 2200:
        return jsonify(success=False, message="Choose a valid year."), 400
    chart_data = DashboardRepository.get_monthly_chart(year)
    return jsonify(chart_data)

@dashboard_bp.route("/api/dashboard/export-students")
@login_required
@role_required("admin", "faculty")
def export_students_csv():
    dept_id = request.args.get("dept_id", None, type=int)
    status = request.args.get("status", None)
    search = request.args.get("search", None)

    # Export every matching row; preserve directory filters and sort order.
    data = StudentRepository.get_all(search=search, dept_id=dept_id, status=status, sort_col=request.args.get("sort_col", "roll_no"), sort_dir=request.args.get("sort_dir", "asc"), per_page=None)
    students = data["items"]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Roll No", "First Name", "Last Name", "Email", "Phone", "Department", "Semester", "Status", "Admission Date", "Average Marks"])

    for s in students:
        writer.writerow([safe_csv(value) for value in [
            s["roll_no"], s["first_name"], s["last_name"], s["email"],
            s["phone"], s["dept_code"], s["current_semester"], s["status"],
            s["admission_date"], s["average_marks"]
        ]])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=hogwards_students_export.csv"}
    )



def safe_csv(value):
    # Prevent spreadsheet formula execution when opening exported user input.
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r", "\n")):
        return "'" + value
    return value


@dashboard_bp.route("/api/search")
@login_required
@role_required("admin", "faculty")
def workspace_search():
    term = request.args.get("q", "").strip()[:100]
    if not term:
        return jsonify(results=[])
    students = StudentRepository.get_all(search=term, per_page=5)["items"]
    courses = db_pool.execute_query("SELECT course_id, course_code, title, dept_id FROM course WHERE course_code LIKE %s OR title LIKE %s ORDER BY course_code LIMIT 5", (f"%{term}%", f"%{term}%"), fetch="all")
    results = [{"title": s["full_name"], "subtitle": f"{s['roll_no']} · {s['dept_code']}", "kind": "Student", "url": url_for("students.profile_view", student_id=s["student_id"])} for s in students]
    results += [{"title": c["title"], "subtitle": c["course_code"], "kind":"Course", "url":url_for("academics.courses_view", search=c["course_code"])} for c in courses]
    pages = [("Students", "students.list_view"), ("Faculty", "academics.faculty_view"), ("Courses", "academics.courses_view"), ("Departments", "academics.departments_view"), ("Course offerings", "academics.offerings_view"), ("Enrollments", "operations.enrollments_view"), ("Attendance", "operations.attendance_view"), ("Results", "operations.results_view"), ("Admissions", "admissions.admissions_view")]
    if session.get("role") == "admin":
        pages += [("Fees and payments", "fees.fees_view"), ("Database insights", "insights.insights_view")]
    results = [{"title":name, "subtitle":"Your workspace", "kind":"Page", "url":url_for(endpoint)} for name, endpoint in pages if term.lower() in name.lower()] + results
    return jsonify(results=results)
