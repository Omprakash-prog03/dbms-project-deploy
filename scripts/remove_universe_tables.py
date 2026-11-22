#!/usr/bin/env python3
"""Remove the Marvel & DC Universe demonstration tables from this installation.

    python scripts/remove_universe_tables.py           # show what would be dropped
    python scripts/remove_universe_tables.py --yes     # drop the 14 tables + 7 views

Only the `uni_` tables and the seven `v_uni_` views are ever touched. Every campus
table (students, fees, courses, attendance, results, users) is left exactly as it is,
and the script refuses to run without `--yes` so it cannot be fired off by accident.

This does not remove the screens from the running application: those ship with the
branch. Check out a branch without the module if you want both gone, or leave the
tables in place -- an empty module shows a friendly "not loaded yet" page.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TABLES = [                      # child tables first, so nothing is orphaned mid-way
    'uni_relationship', 'uni_battle_participation', 'uni_battle', 'uni_organization',
    'uni_mission_participation', 'uni_mission', 'uni_comic', 'uni_content',
    'uni_character_power', 'uni_power', 'uni_membership', 'uni_team',
    'uni_character', 'uni_universe',
]
VIEWS = [
    'v_uni_character_profile', 'v_uni_universe_summary', 'v_uni_team_roster',
    'v_uni_power_distribution', 'v_uni_battle_summary', 'v_uni_relationship_network',
    'v_uni_screen_catalogue',
]


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--yes', action='store_true', help='actually drop them')
    args = parser.parse_args()

    from repositories.db_pool import db_pool

    present = []
    for table in TABLES:
        try:
            rows = db_pool.execute_query(f'SELECT COUNT(*) AS n FROM {table}', fetch='val')
            present.append((table, rows))
        except Exception:
            present.append((table, None))

    found = [(table, rows) for table, rows in present if rows is not None]
    if not found:
        print('Nothing to remove: no uni_ tables exist in this database.')
        return 0

    print('These are the only objects this script will remove:\n')
    for table, rows in found:
        print(f'  table {table:<28} {rows:>6,} rows')
    for view in VIEWS:
        print(f'  view  {view}')

    if not args.yes:
        print('\nNothing was changed. Re-run with --yes to drop them.')
        return 0

    for view in VIEWS:
        db_pool.execute_dml(f'DROP VIEW IF EXISTS {view}')
    for table, _rows in found:
        db_pool.execute_dml(f'DROP TABLE IF EXISTS {table}')

    remaining = []
    for table, _rows in present:
        try:
            db_pool.execute_query(f'SELECT COUNT(*) AS n FROM {table}', fetch='val')
            remaining.append(table)
        except Exception:
            pass
    if remaining:
        raise SystemExit(f'These tables still exist: {remaining}')
    print('\nRemoved 14 uni_ tables and 7 v_uni_ views. No campus table was touched.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
