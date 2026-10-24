from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, abort
import bcrypt
from extensions import limiter
from repositories.db_pool import db_pool

auth_bp = Blueprint("auth", __name__)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"error": "Unauthorized", "message": "Login required"}), 401
            return redirect(url_for("auth.login_view"))
        return f(*args, **kwargs)
    return decorated_function

def role_required(*allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if "user_id" not in session:
                if request.path.startswith("/api/"):
                    return jsonify(success=False, message="Login required"), 401
                return redirect(url_for("auth.login_view"))
            user_role = session.get("role")
            if user_role not in allowed_roles:
                if request.is_json or request.path.startswith("/api/"):
                    return jsonify({"error": "Forbidden", "message": "Access restricted by database role policy"}), 403
                abort(403, description="This area is only available to authorized campus staff.")
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@auth_bp.route("/login", methods=["GET"])
def login_view():
    if "user_id" in session:
        return redirect(url_for("dashboard.dashboard_view"))
    return render_template("login.html")

@auth_bp.route("/api/auth/login", methods=["POST"])
@limiter.limit("10 per minute")
def login_api():
    data = request.get_json(silent=True) or request.form
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"success": False, "message": "Username and password are required."}), 400

    user = db_pool.execute_query(
        "SELECT * FROM app_user WHERE LOWER(username) = LOWER(%s)",
        (username,),
        fetch="one"
    )

    if not user:
        return jsonify({"success": False, "message": "Invalid username or password."}), 401

    # Verify password hash
    stored_hash = user["password_hash"].encode("utf-8") if isinstance(user["password_hash"], str) else user["password_hash"]
    try:
        is_valid = bcrypt.checkpw(password.encode("utf-8"), stored_hash)
    except (ValueError, TypeError):
        # Fail closed. An invalid hash must never authorize a demo password.
        is_valid = False

    if not is_valid:
        return jsonify({"success": False, "message": "Invalid username or password."}), 401

    if user.get("student_id"):
        status = db_pool.execute_query("SELECT status FROM student WHERE student_id = %s", (user["student_id"],), fetch="val")
        if status not in ("Active", "Graduated"):
            return jsonify(success=False, message="This account is inactive. Please contact the university office."), 403
    if user.get("faculty_id"):
        status = db_pool.execute_query("SELECT status FROM faculty WHERE faculty_id = %s", (user["faculty_id"],), fetch="val")
        if status != "Active":
            return jsonify(success=False, message="This account is inactive. Please contact the university office."), 403
    # Rotate the session and CSRF token when privileges change.
    import secrets
    session.clear()
    session["csrf_token"] = secrets.token_urlsafe(32)
    session.permanent = True
    session["user_id"] = user["user_id"]
    session["username"] = user["username"]
    session["role"] = user["role"]
    session["student_id"] = user.get("student_id")
    session["faculty_id"] = user.get("faculty_id")

    destination = url_for("students.profile_view", student_id=user["student_id"]) if user["role"] == "student" else url_for("dashboard.dashboard_view")
    return jsonify({"success": True, "redirect": destination, "role": user["role"]})

@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("Successfully signed out.", "info")
    return redirect(url_for("auth.login_view"))

@auth_bp.route("/api/users/reset-password", methods=["POST"])
@login_required
@role_required("admin")
def reset_password_api():
    """
    Administrative password reset endpoint for students and faculty members.
    Generates a secure bcrypt salt and updates the credentials in app_user.
    """
    data = request.get_json(silent=True) or request.form
    target_type = (data.get("user_type") or "").strip().lower()
    target_id = data.get("target_id")
    new_password = data.get("new_password") or ""

    if len(new_password) < 8 or len(new_password.encode("utf-8")) > 72:
        return jsonify({"success": False, "message": "Use at least 8 characters and at most 72 UTF-8 bytes for your password."}), 400

    new_hash = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    if target_type == "student":
        student = db_pool.execute_query("SELECT student_id, roll_no, email FROM student WHERE student_id = %s", (target_id,), fetch="one")
        if not student:
            return jsonify({"success": False, "message": "Student record not found."}), 404

        user = db_pool.execute_query("SELECT user_id, username FROM app_user WHERE student_id = %s", (target_id,), fetch="one")
        if user:
            db_pool.execute_dml("UPDATE app_user SET password_hash = %s WHERE user_id = %s", (new_hash, user["user_id"]))
            username = user["username"]
        else:
            username = student["roll_no"].lower()
            db_pool.execute_dml(
                "INSERT INTO app_user (username, password_hash, role, student_id, faculty_id) VALUES (%s, %s, 'student', %s, NULL)",
                (username, new_hash, target_id)
            )
        return jsonify({"success": True, "message": f"Password for student '{username}' successfully updated."})

    elif target_type == "faculty":
        fac = db_pool.execute_query("SELECT faculty_id, first_name, last_name, email FROM faculty WHERE faculty_id = %s", (target_id,), fetch="one")
        if not fac:
            return jsonify({"success": False, "message": "Faculty record not found."}), 404

        user = db_pool.execute_query("SELECT user_id, username FROM app_user WHERE faculty_id = %s", (target_id,), fetch="one")
        if user:
            db_pool.execute_dml("UPDATE app_user SET password_hash = %s WHERE user_id = %s", (new_hash, user["user_id"]))
            username = user["username"]
        else:
            username = fac["email"].split("@")[0].lower()
            db_pool.execute_dml(
                "INSERT INTO app_user (username, password_hash, role, faculty_id, student_id) VALUES (%s, %s, 'faculty', %s, NULL)",
                (username, new_hash, target_id)
            )
        return jsonify({"success": True, "message": f"Password for faculty '{username}' successfully updated."})

    elif target_type == "user":
        user = db_pool.execute_query("SELECT user_id, username FROM app_user WHERE user_id = %s", (target_id,), fetch="one")
        if not user:
            return jsonify({"success": False, "message": "User account not found."}), 404
        db_pool.execute_dml("UPDATE app_user SET password_hash = %s WHERE user_id = %s", (new_hash, user["user_id"]))
        return jsonify({"success": True, "message": f"Password for account '{user['username']}' successfully updated."})

    else:
        return jsonify({"success": False, "message": "Invalid user_type. Expected 'student', 'faculty', or 'user'."}), 400
