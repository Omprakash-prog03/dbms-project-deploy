"""Create the campus administrators and the supreme account in one run.

The requested accounts:

    omprakash      OmAdmin123        administrator
    swaruppradhan  Adminpradhan123   administrator
    avashbadatya   Adminavash123     administrator
    aryandash      Adminaryan123     administrator
    om-2026        Superadmin123     supreme administrator (signs in at /supreme)

Existing accounts get the password listed here (that is the point of the
script); pass ``--keep-passwords`` to leave accounts that already exist alone.

    python scripts/setup_admins.py                 # show what would happen
    python scripts/setup_admins.py --apply         # create/update the accounts
    python scripts/setup_admins.py --apply --keep-passwords
    python scripts/setup_admins.py --apply --no-supreme   # admins only

Passwords are hashed with bcrypt and never printed back.
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bcrypt

from config import BASE_DIR, Config
from repositories.db_pool import db_pool

SUPREME = {'username': 'om-2026', 'password': 'Superadmin123', 'role': 'admin'}

ADMINS = [
    {'username': 'omprakash', 'password': 'OmAdmin123', 'role': 'admin'},
    {'username': 'swaruppradhan', 'password': 'Adminpradhan123', 'role': 'admin'},
    {'username': 'avashbadatya', 'password': 'Adminavash123', 'role': 'admin'},
    {'username': 'aryandash', 'password': 'Adminaryan123', 'role': 'admin'},
]


def hash_password(password):
    if len(password) < 8 or len(password.encode('utf-8')) > 72:
        raise SystemExit(f'Password for an account is outside 8..72 bytes: {password!r}')
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def find(username):
    return db_pool.execute_query(
        "SELECT user_id, username, role FROM app_user WHERE LOWER(username) = LOWER(%s)",
        (username,), fetch='one')


def write_account(account, reset, apply):
    username = account['username']
    row = find(username)
    if row is None:
        print(f'  create  {username:<14} {account["role"]}')
        if apply:
            db_pool.execute_dml(
                "INSERT INTO app_user (username, password_hash, role) VALUES (%s, %s, %s)",
                (username, hash_password(account['password']), account['role']))
        return 'created'
    if row['role'] != account['role']:
        print(f'  skip    {username:<14} exists with role {row["role"]} — left alone')
        return 'skipped'
    if reset:
        print(f'  reset   {username:<14} password set as requested')
        if apply:
            db_pool.execute_dml(
                "UPDATE app_user SET password_hash = %s WHERE user_id = %s",
                (hash_password(account['password']), row['user_id']))
        return 'reset'
    print(f'  keep    {username:<14} already exists (use --reset-passwords to replace)')
    return 'kept'


def point_env_at_supreme(supreme_name, apply):
    """A stale OWNER_USERNAME in .env must not steal the supreme seat."""
    env_path = Path(os.getenv('HOGWARDS_ENV_FILE') or (BASE_DIR / '.env'))
    if not env_path.exists():
        return
    lines = env_path.read_text().splitlines()
    changed = False
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith('#') or '=' not in stripped:
            continue
        key, _, value = stripped.partition('=')
        if key.strip() == 'OWNER_USERNAME' and value.strip().strip('"').lower() != supreme_name:
            lines[index] = f'OWNER_USERNAME={supreme_name}'
            changed = True
    if changed:
        print(f'  .env    OWNER_USERNAME set to {supreme_name}')
        if apply:
            env_path.write_text('\n'.join(lines) + '\n')


def main():
    parser = argparse.ArgumentParser(description='Create the NIST administrators and the supreme account.')
    parser.add_argument('--apply', action='store_true', help='write the changes (default: dry run)')
    parser.add_argument('--keep-passwords', action='store_true',
                        help='leave accounts that already exist exactly as they are')
    parser.add_argument('--no-supreme', action='store_true', help='skip the supreme account')
    args = parser.parse_args()

    supreme_name = SUPREME['username']
    print(f'Database: {"MySQL" if db_pool.is_mysql else "SQLite"} · '
          f'{"applying" if args.apply else "dry run (add --apply to write)"}')
    print(f'Supreme account: {supreme_name} · signs in at /supreme')

    reset = not args.keep_passwords
    outcomes = []
    if not args.no_supreme:
        outcomes.append(write_account(SUPREME, reset, args.apply))
        point_env_at_supreme(supreme_name, args.apply)
    for account in ADMINS:
        outcomes.append(write_account(account, reset, args.apply))

    print()
    print('Administrators sign in with username + password:', ', '.join(a['username'] for a in ADMINS))
    if not args.apply:
        print('Nothing was written. Re-run with --apply.')
    else:
        print('Done. Reload the web app, then sign in at /supreme.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
