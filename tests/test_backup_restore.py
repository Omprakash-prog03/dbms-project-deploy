"""Backup/restore tests use separate files, never the app or fixture database."""
from contextlib import closing
from pathlib import Path
import sqlite3
from types import SimpleNamespace
import pytest
from config import Config
from scripts import backup, restore


def database(path, value):
    with closing(sqlite3.connect(path)) as conn:
        conn.executescript('CREATE TABLE student (student_id INTEGER); CREATE TABLE app_user (user_id INTEGER); CREATE TABLE marker (value TEXT);')
        conn.execute('INSERT INTO marker VALUES (?)',(value,))
        conn.commit()


def marker(path):
    with closing(sqlite3.connect(path)) as conn:
        return conn.execute('SELECT value FROM marker').fetchone()[0]


def test_online_backup_includes_committed_wal_data(tmp_path, monkeypatch):
    source = tmp_path/'current.db'
    database(source,'before')
    monkeypatch.setattr(backup,'BASE_DIR',tmp_path)
    monkeypatch.setattr(backup,'db_pool',SimpleNamespace(is_mysql=False,db_path=source))
    with closing(sqlite3.connect(source)) as conn:
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA wal_autocheckpoint=0')
        conn.execute("UPDATE marker SET value='committed in WAL'")
        conn.commit()
        backup.main()
        snapshots = list((tmp_path/'backups').glob('*.db'))
        assert len(snapshots) == 1
        assert marker(snapshots[0]) == 'committed in WAL'
        assert snapshots[0].stat().st_mode & 0o777 == 0o600


def test_restore_requires_confirmation_and_preserves_current_snapshot(tmp_path,monkeypatch):
    source, destination = tmp_path/'selected.db', tmp_path/'current.db'
    database(source,'restored')
    database(destination,'before')
    monkeypatch.setattr(Config,'DB_ENGINE','sqlite')
    monkeypatch.setattr(Config,'SQLITE_PATH',str(destination))
    monkeypatch.setattr(restore,'BASE_DIR',tmp_path)
    monkeypatch.setattr('sys.argv',['restore.py',str(source)])
    with pytest.raises(SystemExit,match='No changes made'):
        restore.main()
    assert marker(destination) == 'before'
    monkeypatch.setattr('sys.argv',['restore.py',str(source),'--confirm'])
    restore.main()
    assert marker(destination) == 'restored'
    snapshots = list((tmp_path/'backups').glob('before_restore_*.db'))
    assert len(snapshots) == 1
    assert marker(snapshots[0]) == 'before'
    assert snapshots[0].stat().st_mode & 0o777 == 0o600


def test_restore_rejects_ambiguous_auto_engine(tmp_path,monkeypatch):
    source = tmp_path/'selected.db'
    database(source,'test')
    monkeypatch.setattr(Config,'DB_ENGINE','auto')
    monkeypatch.setattr('sys.argv',['restore.py',str(source),'--confirm'])
    with pytest.raises(SystemExit,match='explicitly'):
        restore.main()
