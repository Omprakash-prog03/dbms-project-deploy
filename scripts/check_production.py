"""Read-only deployment checks. Does not print secrets, hashes, or personal records."""
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ['APP_ENV'] = 'production'


def main():
    import bcrypt
    from wsgi import application
    from repositories.db_pool import db_pool
    if not db_pool.execute_query("SELECT user_id FROM app_user WHERE role='admin' LIMIT 1", fetch='one'):
        raise SystemExit('No administrator exists. Run the private initializer first.')
    for username, default in (('admin', 'admin123'), ('faculty', 'faculty123'), ('student', 'student123')):
        user = db_pool.execute_query('SELECT password_hash FROM app_user WHERE username=%s', (username,), fetch='one')
        if user and bcrypt.checkpw(default.encode(), user['password_hash'].encode()):
            raise SystemExit('A shared demo credential is still active. Do not publish this database.')
    # A private installation must never carry sample student records.
    seeded = db_pool.execute_query('SELECT COUNT(*) FROM student', fetch='val') or 0
    demo_emails = db_pool.execute_query("SELECT COUNT(*) FROM student WHERE email LIKE '%%@sims.edu'", fetch='val') or 0
    if demo_emails:
        raise SystemExit(f'This database contains {demo_emails} sample records ({seeded} students). '
                         'Initialize a fresh private database instead of publishing demo data.')
    client = application.test_client()
    response = client.get('/healthz')
    if response.status_code != 200:
        raise SystemExit('The database health check failed.')
    if client.get('/dashboard').status_code != 302:
        raise SystemExit('Unauthenticated workspace access was not blocked.')
    login = client.get('/login')
    if b'data-demo=' in login.data:
        raise SystemExit('Demo shortcuts must not be published.')
    if application.config['DEBUG'] or not application.config['RATELIMIT_ENABLED']:
        raise SystemExit('Disable debug mode and enable login rate limiting.')
    print('PASS: private administrator, no shared demo passwords, database ready, authenticated workspace, HTTPS cookies, CSRF, login rate limiting, production headers, and debug disabled.')
    print('The application is ready to attach to the host WSGI configuration. These checks do not publish a website.')


if __name__ == '__main__':
    main()
