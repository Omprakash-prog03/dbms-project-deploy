from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, session, abort
from routes.auth import login_required, role_required
from repositories.students import StudentRepository
from repositories.faculty import FacultyRepository
from repositories.validation import student_fields

student_bp = Blueprint("students", __name__)

@student_bp.route("/students")
@login_required
@role_required("admin", "faculty")
def list_view():
    search = request.args.get("search", "").strip() or None
    dept_id = request.args.get("dept_id", None, type=int)
    status = request.args.get("status", "All")
    sort_col = request.args.get("sort_col", "roll_no")
    sort_dir = "desc" if request.args.get("sort_dir", "asc") == "desc" else "asc"
    if sort_col not in StudentRepository.ALLOWED_SORT_COLUMNS:
        sort_col = "roll_no"
    page = request.args.get("page", 1, type=int)

    data = StudentRepository.get_all(
        search=search,
        dept_id=dept_id,
        status=status,
        sort_col=sort_col,
        sort_dir=sort_dir,
        page=page,
        per_page=15
    )
    departments = FacultyRepository.get_departments()

    return render_template(
        "students/list.html",
        students=data["items"],
        total=data["total"],
        page=data["page"],
        pages=data["pages"],
        departments=departments,
        search=search or "",
        dept_id=dept_id,
        status=status,
        sort_col=sort_col,
        sort_dir=sort_dir
    )

@student_bp.route("/students/<int:student_id>")
@login_required
def profile_view(student_id):
    if session.get("role") == "student" and student_id != session.get("student_id"):
        abort(403, description="You can only view your own student profile.")
    student = StudentRepository.get_by_id(student_id)
    if not student:
        flash("Student profile not found.", "error")
        return redirect(url_for("students.list_view"))

    guardians = StudentRepository.get_guardians(student_id)
    enrollments = StudentRepository.get_enrollments(student_id)
    results = StudentRepository.get_results(student_id)
    fee_summary = StudentRepository.get_fee_summary(student_id) if session.get("role") in ("admin", "student") else []

    # Get student audit log rows
    from repositories.db_pool import db_pool
    audit_rows = db_pool.execute_query(
        "SELECT * FROM audit_log WHERE table_name = 'student' AND record_id = %s ORDER BY changed_at DESC LIMIT 10",
        (student_id,), fetch="all"
    ) if session.get("role") == "admin" else []

    return render_template(
        "students/profile.html",
        student=student,
        guardians=guardians,
        enrollments=enrollments,
        results=results,
        fee_summary=fee_summary,
        audit_rows=audit_rows
    )

@student_bp.route("/api/students/create", methods=["POST"])
@login_required
@role_required("admin", "faculty")
def create_student():
    data = request.get_json(silent=True) or request.form
    try:
        new_id = StudentRepository.create(**student_fields(data))
        return jsonify({"success": True, "student_id": new_id, "message": "Student created successfully."})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400

@student_bp.route("/api/students/update/<int:student_id>", methods=["POST"])
@login_required
@role_required("admin")
def update_student(student_id):
    data = request.get_json(silent=True) or request.form
    try:
        existing = StudentRepository.get_by_id(student_id)
        if not existing:
            return jsonify(success=False, message="Student record not found."), 404
        StudentRepository.update(student_id=student_id, **student_fields(data, existing))
        return jsonify({"success": True, "message": "Student updated successfully."})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400

@student_bp.route("/api/students/delete/<int:student_id>", methods=["POST"])
@login_required
@role_required("admin")
def delete_student(student_id):
    try:
        StudentRepository.delete(student_id)
        return jsonify({"success": True, "message": "Student removed."})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400
