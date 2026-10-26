import os
import secrets
import hmac
import threading
from collections import OrderedDict
from datetime import date, datetime
from flask import Flask, jsonify, request, session, abort, render_template, redirect, url_for, flash
from werkzeug.exceptions import HTTPException
from config import Config
from extensions import limiter
from werkzeug.middleware.proxy_fix import ProxyFix
from repositories.db_pool import db_pool, get_last_queries, clear_last_queries
from repositories import admin_sessions
from repositories import login_history
from repositories import staff_activity
from repositories import owner as owner_guard


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    if app.config['APP_ENV'] == 'production':
        if not app.config.get('SECRET_KEY') or len(app.config['SECRET_KEY']) < 32:
            raise RuntimeError('Production requires a persistent SECRET_KEY of at least 32 characters.')
        if app.config['DEMO_MODE']:
            raise RuntimeError('Demo mode must be disabled in production.')
        if not app.config['SESSION_COOKIE_SECURE'] or not app.config['CSRF_ENABLED']:
            raise RuntimeError('Production requires HTTPS cookies and CSRF protection.')
        if app.config['DB_ENGINE'] == 'auto':
            raise RuntimeError('Select a database engine explicitly in production.')
    if app.config['TRUSTED_PROXY_HOPS']:
        # Enable only when the application is accessible through that many trusted
        # proxies. PythonAnywhere uses one trusted front-end proxy.
        hops = app.config['TRUSTED_PROXY_HOPS']
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=hops, x_proto=hops)
    limiter.init_app(app)
    app.jinja_env.globals.update(
        portal_name=app.config['PORTAL_NAME'],
        portal_short_name=app.config['PORTAL_SHORT_NAME'],
        portal_descriptor=app.config['PORTAL_DESCRIPTOR'],
    )
    from routes.auth import auth_bp, login_required, role_required
    from routes.dashboard import dashboard_bp
    from routes.students import student_bp
    from routes.academics import academics_bp
    from routes.operations import operations_bp
    from routes.fees import fee_bp
    from routes.admissions import admissions_bp
    from routes.insights import insights_bp
    from routes.reports import reports_bp
    from routes.rawdata import rawdata_bp
    from routes.owner import owner_bp
    for blueprint in (auth_bp, dashboard_bp, student_bp, academics_bp, operations_bp, fee_bp, admissions_bp, insights_bp, reports_bp, rawdata_bp, owner_bp):
        app.register_blueprint(blueprint)

    # The guard and the session registry are additive tables; create them up front
    # so the very first sign-in never has to build them mid-request.
    try:
        owner_guard.ensure_schema()
        admin_sessions.ensure_schema()
        login_history.ensure_schema()
        staff_activity.ensure_schema()
    except Exception:  # a read-only database must not stop the app from booting
        app.logger.warning('Could not prepare the owner tables at startup', exc_info=True)

    # Bounded, per-session query traces. Never a process-global feed of other users' SQL.
    traces = OrderedDict()
    trace_lock = threading.Lock()

    @app.before_request
    def before_req():
        clear_last_queries()
        if request.path.startswith('/static/') or request.endpoint == 'health':
            return
        if request.path.startswith('/api/') and request.method in ('POST','PUT','PATCH') and request.is_json:
            payload = request.get_json(silent=True)
            if not isinstance(payload, dict):
                return jsonify(success=False, message='Send a JSON object with the required fields.'), 400
            text_fields = {'username','password','first_name','last_name','email','phone','dob','admission_date','gender','address','roll_no','status','course_code','title','designation','hire_date','academic_year','term','class_date','mode','receipt_no','user_type','new_password','initial_password','dept_code','dept_name','applicant_name','exam_type','exam_date','password'}
            if any(key in payload and not isinstance(payload[key], str) for key in text_fields):
                return jsonify(success=False, message='Text fields must contain text values.'), 400
        if 'csrf_token' not in session:
            session['csrf_token'] = secrets.token_urlsafe(32)
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE') and app.config['CSRF_ENABLED']:
            token = request.headers.get('X-CSRF-Token') or request.form.get('csrf_token', '')
            if not hmac.compare_digest(str(token), session['csrf_token']):
                if request.path.startswith('/api/'):
                    return jsonify(success=False, message='Your session expired. Refresh the page and try again.'), 400
                abort(400, description='Refresh the page and try again.')

        # Owner guard. A lockdown ends every administrator session except the
        # owner's; a non-owner administrator only stays signed in while both the
        # owner's current epoch and their access approval still hold.
        if session.get('role') == 'admin' and request.endpoint not in ('auth.login_view', 'static'):
            username = session.get('username', '')
            owner_here = owner_guard.is_owner(username)
            stale = (not owner_guard.session_is_current()
                     or int(session.get('admin_token_version') or 0) != admin_sessions.version(username))
            if owner_here:
                if stale:
                    # The owner re-stamps: a lockdown never ends the owner's own session.
                    session['admin_token_version'] = admin_sessions.version(username)
                    owner_guard.stamp_session()
                admin_sessions.touch(username, request.remote_addr or '')
            elif stale or not session.get('access_approved'):
                ended_by_owner = owner_guard.session_is_current()
                session.clear()
                message = ('The owner ended your administrator session. Ask them for a new access code.'
                           if ended_by_owner else
                           'This administrator session is no longer valid. Sign in again with an access code.')
                if request.path.startswith('/api/') or request.is_json:
                    return jsonify(success=False, code='owner_signed_out', message=message), 401
                flash(message, 'info')
                return redirect(url_for('auth.login_view'))
            else:
                admin_sessions.touch(username, request.remote_addr or '')

    @app.after_request
    def after_req(response):
        # Who changed what: one line per successful admin/faculty change.
        try:
            staff_activity.capture_request(response)
        except Exception:
            pass
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        if app.config['APP_ENV'] == 'production' and not app.config['EMBEDDED_PREVIEW']:
            response.headers['X-Frame-Options'] = 'SAMEORIGIN'
            response.headers['Content-Security-Policy'] = "frame-ancestors 'self'; object-src 'none'; base-uri 'self'"
            response.headers['Strict-Transport-Security'] = 'max-age=31536000'
            response.headers['X-Robots-Tag'] = 'noindex, nofollow'
        # Development previews can be embedded without weakening production.
        if not request.path.startswith('/static/'):
            response.headers['Cache-Control'] = 'no-store'
        if session.get('role') == 'admin' and request.endpoint and not request.endpoint.startswith(('auth.', 'static', 'inspect_sql')):
            queries = get_last_queries()
            if queries:
                trace_id = session.setdefault('_sql_trace', secrets.token_urlsafe(24))
                with trace_lock:
                    traces[trace_id] = queries
                    traces.move_to_end(trace_id)
                    while len(traces) > 128:
                        traces.popitem(last=False)
        return response

    @app.context_processor
    def inject_globals():
        is_owner = session.get('role') == 'admin' and owner_guard.is_owner(session.get('username'))
        names = {'dashboard':'Overview', 'students':'Students', 'faculty':'Faculty', 'departments':'Departments', 'courses':'Courses', 'offerings':'Course offerings', 'enrollments':'Enrollments', 'attendance':'Attendance', 'results':'Results', 'fees':'Fees & payments', 'admissions':'Admissions', 'insights':'Database insights', 'reports':'Reports & PDF', 'raw-data':'Raw data', 'admin-access':'Supreme control', 'owner':'Supreme control'}
        pending_count = 0
        if session.get('role') in ('admin', 'faculty'):
            pending_count = db_pool.execute_query("SELECT COUNT(*) FROM admission_application WHERE status='Pending'", fetch='val') or 0
        return {
            'current_user': {'user_id':session.get('user_id'), 'username':session.get('username','Guest'), 'role':session.get('role','visitor')},
            'is_mysql': db_pool.is_mysql, 'db_name':Config.DB_NAME,
            'csrf_token':session.get('csrf_token',''), 'today':date.today(),
            'pending_count':pending_count, 'page_name':names.get(request.path.strip('/').split('/')[0], 'Workspace'),
            'demo_mode':app.config['DEMO_MODE'],
            'is_owner': is_owner,
            'owner_name': owner_guard.owner_username() if is_owner else '',
            'owner_pending': owner_guard.pending_count() if is_owner else 0,
        }

    @app.template_filter('initials')
    def initials(value):
        parts = str(value or '').split()
        return ''.join(part[0].upper() for part in parts[:2])

    @app.template_filter('short_date')
    def short_date(value):
        if not value:
            return '—'
        if isinstance(value, (date, datetime)):
            return value.strftime('%d %b %Y')
        try:
            return date.fromisoformat(str(value)[:10]).strftime('%d %b %Y')
        except ValueError:
            return str(value)

    @app.template_filter('compact_inr')
    def compact_inr(value):
        value = float(value or 0)
        if value >= 10000000:
            return f'₹{value / 10000000:.2f}Cr'
        if value >= 100000:
            return f'₹{value / 100000:.1f}L'
        if value >= 1000:
            return f'₹{value / 1000:.1f}K'
        return f'₹{value:,.0f}'

    @app.route('/api/inspect-sql')
    @login_required
    @role_required('admin')
    def inspect_sql():
        with trace_lock:
            queries = traces.get(session.get('_sql_trace'), [])
        return jsonify(engine='MySQL 8' if db_pool.is_mysql else 'SQLite · Embedded relational engine', database=Config.DB_NAME, queries=queries, count=len(queries))

    @app.route('/healthz')
    def health():
        try:
            db_pool.execute_query('SELECT user_id FROM app_user LIMIT 1', fetch='one')
            return jsonify(status='ok', application=app.config['PORTAL_NAME'])
        except Exception:
            app.logger.exception('Database health check failed')
            return jsonify(status='unavailable'), 503

    @app.errorhandler(429)
    def too_many_requests(error):
        return jsonify(success=False, message='Too many sign-in attempts. Wait a minute and try again.'), 429

    @app.errorhandler(HTTPException)
    def http_error(error):
        if request.path.startswith('/api/'):
            return jsonify(success=False, message=error.description), error.code
        return render_template('error.html', code=error.code, message=error.description), error.code

    @app.errorhandler(ValueError)
    @app.errorhandler(TypeError)
    @app.errorhandler(KeyError)
    def invalid_input(error):
        if request.path.startswith('/api/'):
            return jsonify(success=False, message='Please check the required fields and enter valid values.'), 400
        raise error

    return app

app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
