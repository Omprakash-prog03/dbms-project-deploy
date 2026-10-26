"""Create, replace or check the owner's master key (the "PIN").

The key is only ever stored as a bcrypt hash, so this script is also the
recovery path if the owner loses it.

    python scripts/owner_key.py --generate           # print a new key, store its hash
    python scripts/owner_key.py --set 'my long key'  # use a key you chose
    python scripts/owner_key.py --check 'my long key'
    python scripts/owner_key.py --status
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config  # noqa: E402
from repositories import owner  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description='Manage the portal owner master key.')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--generate', action='store_true', help='create a random key and print it once')
    group.add_argument('--set', metavar='KEY', help='use this key instead')
    group.add_argument('--check', metavar='KEY', help='verify a key without changing it')
    group.add_argument('--status', action='store_true', help='show whether a key exists')
    parser.add_argument('--owner', default='', help='owner username, recorded in the audit trail')
    args = parser.parse_args()

    if args.check:
        print('Match.' if owner.verify_master_key(args.check) else 'No match.')
        return 0 if owner.verify_master_key(args.check) else 1
    if args.status:
        print(f'Owner account: {owner.owner_username() or "(no admin yet)"}')
        print('Master key:    ' + (f'set ({owner.master_key_hint()})' if owner.master_key_set() else 'not set'))
        print('Lock epoch:    ' + str(owner.epoch()))
        return 0

    key = args.set or owner.generate_master_key()
    key = key.strip()
    if len(key) < owner.MIN_MASTER_KEY:
        print(f'The key must be at least {owner.MIN_MASTER_KEY} characters.')
        return 2
    owner.set_master_key(key, rotated_by=args.owner or 'command line')
    print('Master key stored (hash only).')
    print()
    print(f'    {key}')
    print()
    print('Write it down now — it cannot be shown again.')
    print('Use it on the portal at  Supreme control  (sidebar, /owner) to sign other')
    print('administrators out and to issue their one-time sign-in codes.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
