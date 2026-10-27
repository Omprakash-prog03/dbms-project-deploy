"""Undo for a real database: a snapshot taken before every writable statement.

Two databases use this: the Oracle practice schema, and — when the studio is
linked to it — the portal's own file. A snapshot is one small SQLite backup, so
a `CREATE TABLE`, an `INSERT` or a `DROP` can be taken back exactly as it was:
structure, rows, triggers, indexes and all.

The stack is kept on disk (`index.json` plus one file per step), which means an
undo still works after the screen, the worker or the whole host has restarted.
`sqlite3.Connection.backup` is used in both directions, so a snapshot is taken
and restored consistently even while other connections are serving requests.
"""
import json
import os
import sqlite3
import uuid
from datetime import datetime


def _short(sql, width=90):
    """A one-line label for the stack, with an ellipsis when it is cut."""
    text = (sql or '').strip()
    return text if len(text) <= width else text[:width - 1].rstrip() + '…'


class Journal:
    """A bounded undo/redo stack of database snapshots."""

    def __init__(self, database, directory, limit=12, noun='change'):
        self.database = str(database)
        self.directory = str(directory)
        self.limit = int(limit)
        self.noun = noun

    # ---------------------------------------------------------------- files --
    def _ensure(self):
        os.makedirs(self.directory, exist_ok=True)
        return self.directory

    def _where(self, name):
        return os.path.join(self.directory, name)

    def _index(self):
        try:
            with open(self._where('index.json'), 'r', encoding='utf-8') as handle:
                raw = json.load(handle)
        except (OSError, ValueError):
            raw = {}
        clean = {'undo': [], 'redo': []}
        for stack in ('undo', 'redo'):
            for item in raw.get(stack) or []:
                if isinstance(item, dict) and item.get('file'):
                    clean[stack].append({
                        'file': str(item['file']),
                        'label': str(item.get('label') or 'a statement'),
                        'verb': str(item.get('verb') or ''),
                        'at': str(item.get('at') or ''),
                    })
        return clean

    def _save(self, state):
        try:
            self._ensure()
            with open(self._where('index.json'), 'w', encoding='utf-8') as handle:
                json.dump(state, handle)
        except OSError:
            pass

    def _drop(self, item):
        try:
            os.remove(self._where(item['file']))
        except OSError:
            pass

    def _freeze(self):
        """A consistent copy of the database, made with SQLite's own backup API."""
        self._ensure()
        name = f'{uuid.uuid4().hex}.db'
        destination = sqlite3.connect(self._where(name))
        source = sqlite3.connect(self.database, timeout=10)
        try:
            source.backup(destination)
        finally:
            destination.close()
            source.close()
        return name

    def _thaw(self, name):
        source = sqlite3.connect(self._where(name), timeout=10)
        destination = sqlite3.connect(self.database, timeout=10)
        try:
            source.backup(destination)
        finally:
            destination.close()
            source.close()

    # ---------------------------------------------------------------- verbs --
    def record(self, sql, verb):
        """Keep the state a statement is about to replace. Never raises."""
        try:
            state = self._index()
            state['undo'].append({
                'file': self._freeze(),
                'label': _short(' '.join((sql or '').split())),
                'verb': verb,
                'at': datetime.now().strftime('%H:%M:%S'),
            })
            for forgotten in state['redo']:
                self._drop(forgotten)
            state['redo'] = []
            while len(state['undo']) > self.limit:
                self._drop(state['undo'].pop(0))
            self._save(state)
            return True
        except (OSError, sqlite3.Error):
            return False

    def forget(self):
        """Drop the newest snapshot: the statement it guarded never landed."""
        try:
            state = self._index()
            if state['undo']:
                self._drop(state['undo'].pop())
                self._save(state)
        except OSError:
            pass

    def state(self):
        state = self._index()
        undo, redo = state['undo'], state['redo']
        return {
            'can_undo': bool(undo), 'can_redo': bool(redo),
            'undo_label': undo[-1]['label'] if undo else '',
            'redo_label': redo[-1]['label'] if redo else '',
            'undo_verb': undo[-1]['verb'] if undo else '',
            'redo_verb': redo[-1]['verb'] if redo else '',
            'depth': len(undo), 'limit': self.limit, 'noun': self.noun,
            'history': [{'label': item['label'], 'verb': item['verb'], 'at': item['at']}
                        for item in reversed(undo[-8:])],
        }

    def _step(self, direction):
        back = direction == 'undo'
        state = self._index()
        source, target = ('undo', 'redo') if back else ('redo', 'undo')
        empty = (f'There is no {self.noun} to undo.' if back
                 else f'There is no undone {self.noun} to replay.')
        if not state[source]:
            return {'ok': False, 'error': empty, 'journal': self.state()}
        entry = state[source][-1]
        if not os.path.exists(self._where(entry['file'])):
            state[source].pop()
            self._save(state)
            return {'ok': False, 'error': 'That snapshot is gone.',
                    'journal': self.state()}
        try:
            frozen = self._freeze()
        except (OSError, sqlite3.Error):
            return {'ok': False, 'error': 'The database is busy; try again.',
                    'journal': self.state()}
        state[source].pop()
        state[target].append({'file': frozen, 'label': entry['label'],
                              'verb': entry['verb'],
                              'at': datetime.now().strftime('%H:%M:%S')})
        while len(state[target]) > self.limit:
            self._drop(state[target].pop(0))
        self._save(state)
        try:
            self._thaw(entry['file'])
        except (OSError, sqlite3.Error):
            return {'ok': False, 'error': 'The snapshot could not be restored.',
                    'journal': self.state()}
        self._drop(entry)
        return {'ok': True,
                'message': (f'Undone: {entry["label"]}' if back
                            else f'Restored: {entry["label"]}'),
                'label': entry['label'], 'verb': entry['verb'],
                'journal': self.state()}

    def undo(self):
        return self._step('undo')

    def redo(self):
        return self._step('redo')

    def clear(self):
        state = self._index()
        for item in state['undo'] + state['redo']:
            self._drop(item)
        self._save({'undo': [], 'redo': []})
