"""Initialize a private installation in a fresh Python process. Never seeds demo data."""
import argparse
import getpass
import json
import os
from pathlib import Path
import re
import secrets
import sys

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))


def initialize(username, password, config_path=None, database_path=None, proxy_hops=0):
    username = username.strip()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{2,49}', username):
        raise ValueError('Use a username of 3–50 letters, digits, dots, underscores, or dashes.')
    if len(password) < 12 or len(password.encode('utf-8')) > 72:
        raise ValueError('Use a private password of at least 12 characters and at most 72 UTF-8 bytes.')
    if proxy_hops not in (0, 1):
        raise ValueError('Choose zero or one trusted hosting proxy.')
    config_path = Path(config_path or BASE_DIR / '.env').resolve()
    database_path = Path(database_path or BASE_DIR / 'instance' / 'hogwards.db').resolve()
    if config_path.exists() or database_path.exists():
        raise FileExistsError('Refusing to overwrite an existing configuration or database. Back it up and use a new target for a fresh installation.')
    if 'repositories.db_pool' in sys.modules:
        raise RuntimeError('Run this initializer in a fresh Python process, not inside a running application.')

    values = {
        'APP_ENV': 'production',
        'SECRET_KEY': secrets.token_hex(32),
        'DB_ENGINE': 'sqlite',
        'SQLITE_PATH': str(database_path),
        'DEMO_MODE': 'false',
        'COOKIE_SECURE': 'true',
        'EMBEDDED_PREVIEW': 'false',
        'TRUSTED_PROXY_HOPS': str(proxy_hops),
    }
    # Config loads these before opening any connection. The existing local/demo
    # database is never copied or used as the production source.
    os.environ.update(values)
    os.environ['HOGWARDS_ENV_FILE'] = str(config_path)
    previous_umask = os.umask(0o077)
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        database_path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        import bcrypt
        from repositories.db_pool import db_pool
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        db_pool.execute_dml("INSERT INTO app_user(username,password_hash,role) VALUES(%s,%s,'admin')", (username, password_hash))
        with os.fdopen(os.open(config_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), 'w') as output:
            output.write('# Private production configuration. Never commit or share this file.\n')
            for key, value in values.items():
                output.write(f'{key}={json.dumps(value)}\n')
        os.chmod(database_path, 0o600)
    finally:
        os.umask(previous_umask)
    return {'config_path': config_path, 'database_path': database_path, 'username': username}


def main():
    parser = argparse.ArgumentParser(description='Initialize an empty, private NIST University Portal Management installation.')
    parser.add_argument('--config-path', type=Path)
    parser.add_argument('--database-path', type=Path)
    parser.add_argument('--proxy-hops', type=int, choices=(0, 1), default=0)
    args = parser.parse_args()
    print('Creates one private administrator and an empty database. No demo accounts or student records are imported.')
    username = input('Administrator username: ').strip()
    password = getpass.getpass('Private password (12+ characters; never sent to chat): ')
    if password != getpass.getpass('Confirm password: '):
        raise SystemExit('Passwords did not match. No changes made.')
    try:
        result = initialize(username, password, args.config_path, args.database_path, args.proxy_hops)
    except (ValueError, FileExistsError, RuntimeError) as error:
        raise SystemExit(str(error))
    print(f"Private installation initialized for {result['username']}.")
    print(f"Database: {result['database_path']}")
    print('Keep the password in your password manager. It is not printed or saved in plaintext.')


if __name__ == '__main__':
    main()
