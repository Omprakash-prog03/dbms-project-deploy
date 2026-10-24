"""Restore an explicitly chosen backup, after the operator stops the web server."""
import argparse
from contextlib import closing
import datetime
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import Config, BASE_DIR


def main():
    parser = argparse.ArgumentParser(description='Restore a Hogwards Student Management System backup. Stop the app and take a current backup first.')
    parser.add_argument('backup', type=Path)
    parser.add_argument('--confirm', action='store_true', help='Confirm that the server is stopped and replacing database contents is intended.')
    args = parser.parse_args()
    source = args.backup.resolve()
    if not source.is_file():
        raise SystemExit('Backup file not found.')
    if not args.confirm:
        raise SystemExit('No changes made. Stop the server, back up the current database, then rerun with --confirm.')
    if source.suffix == '.db':
        if Config.DB_ENGINE != 'sqlite':
            raise SystemExit('Set DB_ENGINE=sqlite explicitly before restoring a SQLite backup.')
        destination = Path(Config.SQLITE_PATH).resolve()
        if source == destination:
            raise SystemExit('The source backup is already the configured database.')
        with closing(sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)) as backup:
            if backup.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise SystemExit('The backup failed SQLite integrity verification.')
            tables = {r[0] for r in backup.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {'student','app_user'}.issubset(tables):
                raise SystemExit('This file is not a Hogwards Student Management System database.')
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                directory = BASE_DIR/'backups'
                directory.mkdir(mode=0o700, exist_ok=True)
                checkpoint = directory/f'before_restore_{datetime.datetime.now():%Y%m%d_%H%M%S_%f}.db'
                os.close(os.open(checkpoint, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600))
                with closing(sqlite3.connect(destination)) as old, closing(sqlite3.connect(checkpoint)) as saved:
                    old.backup(saved)
            else:
                os.close(os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600))
            with closing(sqlite3.connect(destination)) as target:
                backup.backup(target)
        print('SQLite database restored. Restart the app to apply any pending non-destructive migrations.')
    elif source.suffix == '.sql':
        if Config.DB_ENGINE != 'mysql':
            raise SystemExit('Set DB_ENGINE=mysql explicitly before restoring a SQL dump.')
        executable = shutil.which('mysql')
        if not executable:
            raise SystemExit('The MySQL client is required for this restore.')
        def quote(value):
            return '"'+str(value).replace('\\','\\\\').replace('"','\\"').replace('\n','\\n')+'"'
        with tempfile.TemporaryDirectory(prefix='hogwards-restore-') as temp:
            credentials = Path(temp)/'client.cnf'
            credentials.write_text('[client]\nuser='+quote(Config.DB_USER)+'\npassword='+quote(Config.DB_PASSWORD)+'\nhost='+quote(Config.DB_HOST)+'\nport='+str(Config.DB_PORT)+'\n')
            os.chmod(credentials,0o600)
            with source.open('rb') as dump:
                subprocess.run([executable,f'--defaults-extra-file={credentials}',Config.DB_NAME],stdin=dump,check=True)
        print('MySQL dump restored. Review database migrations before restarting the app.')
    else:
        raise SystemExit('Expected a .db or .sql backup. No changes made.')

if __name__ == '__main__':
    main()
