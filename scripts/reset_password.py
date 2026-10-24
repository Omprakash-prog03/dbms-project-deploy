"""Reset an existing portal account password from the server console.

Passwords are typed with hidden input and never accepted as command-line
arguments, so they do not end up in shell history or process listings.
"""
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bcrypt
from config import Config
from repositories.db_pool import db_pool


def main(create_admin=False):
    if Config.APP_ENV == 'production' and not db_pool.execute_query(
        "SELECT user_id FROM app_user WHERE role='admin' LIMIT 1", fetch='one'
    ):
        raise SystemExit('No administrator exists. Run scripts/init_production.py first.')
    username = input('Account username to reset: ').strip()
    user = db_pool.execute_query(
        'SELECT user_id, role FROM app_user WHERE LOWER(username)=LOWER(%s)', (username,), fetch='one'
    )
    if not user:
        if not create_admin:
            raise SystemExit('No account with that username. Nothing was changed. '
                             'Use --create-admin to create a new administrator.')
        print('That username does not exist; a new administrator account will be created.')
    password = getpass.getpass('New password (12+ characters): ')
    if len(password) < 12 or len(password.encode('utf-8')) > 72:
        raise SystemExit('Use at least 12 characters and at most 72 UTF-8 bytes. Nothing was changed.')
    if password != getpass.getpass('Confirm new password: '):
        raise SystemExit('Passwords did not match. Nothing was changed.')
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    if user:
        db_pool.execute_dml('UPDATE app_user SET password_hash=%s WHERE user_id=%s', (hashed, user['user_id']))
        print(f"Password updated for {username} ({user['role']}). Sign in at the portal; existing sessions stay valid until they expire.")
    else:
        db_pool.execute_dml("INSERT INTO app_user (username,password_hash,role) VALUES (%s,%s,'admin')", (username, hashed))
        print(f"Administrator '{username}' created. Sign in at the portal.")


if __name__ == '__main__':
    main('--create-admin' in sys.argv[1:])
