"""Reset an existing portal account password from the server console.

Passwords are typed with hidden input and never accepted as command-line
arguments, so they do not end up in shell history or process listings.
"""
import getpass
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bcrypt
from config import Config
from repositories.db_pool import db_pool


def _lookup(username):
    return db_pool.execute_query(
        'SELECT user_id, username, role, password_hash FROM app_user WHERE LOWER(username)=LOWER(%s)',
        (username,), fetch='one',
    )


def _verify(username, password):
    user = _lookup(username)
    return bool(user) and bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8'))


def main(create_admin=False, random_password=False, check=False):
    if Config.APP_ENV == 'production' and not db_pool.execute_query(
        "SELECT user_id FROM app_user WHERE role='admin' LIMIT 1", fetch='one'
    ):
        raise SystemExit('No administrator exists. Run scripts/init_production.py first.')
    print(f'Database: {Config.SQLITE_PATH if not db_pool.is_mysql else Config.DB_NAME}')
    username = input('Account username to reset: ').strip()
    user = _lookup(username)
    if check:
        if not user:
            raise SystemExit(f'No account named {username!r} in this database.')
        password = getpass.getpass('Password to test: ')
        print('RESULT:', 'MATCH - these credentials work' if _verify(username, password)
              else 'NO MATCH - the stored password is different')
        return
    if not user:
        if not create_admin:
            raise SystemExit('No account with that username. Nothing was changed. '
                             'Use --create-admin to create a new administrator.')
        print('That username does not exist; a new administrator account will be created.')
    if random_password:
        # Avoid hidden-input typos entirely: a one-time password is printed once.
        password = secrets.token_urlsafe(15)
        print(f'Generated password: {password}')
        print('Copy it now; it is not stored in plaintext and will not be shown again.')
    else:
        password = getpass.getpass('New password (12+ characters): ')
    if len(password) < 12 or len(password.encode('utf-8')) > 72:
        raise SystemExit('Use at least 12 characters and at most 72 UTF-8 bytes. Nothing was changed.')
    if not random_password and password != getpass.getpass('Confirm new password: '):
        raise SystemExit('Passwords did not match. Nothing was changed.')
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    if user:
        db_pool.execute_dml('UPDATE app_user SET password_hash=%s WHERE user_id=%s', (hashed, user['user_id']))
        print(f"Password updated for {user['username']} ({user['role']}).")
    else:
        db_pool.execute_dml("INSERT INTO app_user (username,password_hash,role) VALUES (%s,%s,'admin')", (username, hashed))
        print(f"Administrator '{username}' created.")
    print('Verified against the database:', 'OK' if _verify(username, password) else 'FAILED - try again')
    print('Sign in at the portal. Existing sessions expire on their own schedule.')


if __name__ == '__main__':
    main(
        create_admin='--create-admin' in sys.argv[1:],
        random_password='--random' in sys.argv[1:],
        check='--check' in sys.argv[1:],
    )
