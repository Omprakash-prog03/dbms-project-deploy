"""Create an administrator interactively. Never pass a password on the command line."""
import getpass
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bcrypt
from repositories.db_pool import db_pool


def main():
    username = input('New administrator username: ').strip()
    if not username or len(username) > 50:
        raise SystemExit('Choose a username between 1 and 50 characters.')
    if db_pool.execute_query('SELECT user_id FROM app_user WHERE username=%s', (username,), fetch='one'):
        raise SystemExit('That username already exists. No changes made.')
    password = getpass.getpass('New password (8+ characters): ')
    if len(password) < 8 or len(password.encode('utf-8')) > 72:
        raise SystemExit('Use at least 8 characters and at most 72 UTF-8 bytes.')
    if password != getpass.getpass('Confirm password: '):
        raise SystemExit('Passwords did not match. No changes made.')
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    db_pool.execute_dml("INSERT INTO app_user(username,password_hash,role) VALUES(%s,%s,'admin')", (username, hashed))
    print('Administrator created. Sign in through the web portal.')

if __name__ == '__main__':
    main()
