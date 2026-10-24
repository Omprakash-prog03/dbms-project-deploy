"""Snapshot the configured database, without putting passwords in process arguments."""
import os
from contextlib import closing
import sys
import sqlite3
import shutil
import tempfile
import datetime
import subprocess
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import Config, BASE_DIR
from repositories.db_pool import db_pool


def main():
    directory = BASE_DIR / 'backups'
    directory.mkdir(mode=0o700, exist_ok=True)
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    if not db_pool.is_mysql:
        destination = directory / f'hogwards_{stamp}.db'
        # SQLite's online backup API takes a coherent snapshot even with WAL/writes.
        os.close(os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600))
        try:
            with closing(sqlite3.connect(db_pool.db_path)) as source, closing(sqlite3.connect(destination)) as target:
                source.backup(target)
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        print(f'Created SQLite backup: {destination}')
        return
    executable = shutil.which('mysqldump')
    if not executable:
        raise SystemExit('mysqldump is required to back up the configured MySQL database.')
    destination = directory / f'hogwards_{stamp}.sql'
    def option(value):
        return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n') + '"'
    with tempfile.TemporaryDirectory(prefix='hogwards-backup-') as temporary:
        credentials = Path(temporary) / 'client.cnf'
        credentials.write_text('[client]\nuser='+option(Config.DB_USER)+'\npassword='+option(Config.DB_PASSWORD)+'\nhost='+option(Config.DB_HOST)+'\nport='+str(Config.DB_PORT)+'\n')
        os.chmod(credentials, 0o600)
        try:
            with os.fdopen(os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), 'w') as output:
                subprocess.run([executable, f'--defaults-extra-file={credentials}', '--single-transaction', '--routines', '--triggers', Config.DB_NAME], stdout=output, check=True)
        except subprocess.CalledProcessError:
            destination.unlink(missing_ok=True)
            raise SystemExit('Backup failed; the incomplete file was removed.')
    print(f'Created MySQL backup: {destination}')

if __name__ == '__main__':
    main()
