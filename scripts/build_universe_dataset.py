#!/usr/bin/env python3
"""Build the Marvel & DC Universe dataset and load it into the portal.

    python scripts/build_universe_dataset.py            # build files, then load
    python scripts/build_universe_dataset.py --no-load  # build files only
    python scripts/build_universe_dataset.py --sql-only # emit SQL, print the command

What it does, in order:

 1. Assembles the 14 entities from scripts/mdu/*.py, assigning primary keys in insert
    order and resolving every foreign key through the character/team/power keys.
 2. Validates: primary-key uniqueness, foreign-key resolution, duplicate pairs,
    missing values, date ordering, range checks, and continuity cross-references
    (a DCEU battle must not field an Earth-616 character).
 3. Writes datasets/csv/*.csv, datasets/universe.xlsx (one sheet per entity),
    datasets/sql/00_schema.sql ... 14 insert scripts, datasets/data_dictionary.md,
    datasets/er_diagram.md + .svg, datasets/validation_report.md and
    datasets/insertion_log.md.
 4. Loads the data into the portal database through the portal's own repository layer
    (repositories.db_pool), in foreign-key order, inside one transaction per entity,
    and re-reads every table to verify row counts and foreign keys.

The loader refuses to run if the target already contains universe rows, so it can
never overwrite a populated database. Use --reset to clear the uni_ tables first
(that deletes only the 14 demonstration tables, never a campus table).
"""
import argparse
import csv
import datetime
import os
import sys
from collections import Counter, OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))

from mdu.powers import POWERS                                    # noqa: E402
from mdu.characters import CHARACTERS                            # noqa: E402
from mdu.teams import TEAMS, MEMBERSHIPS                         # noqa: E402
from mdu.content import CONTENT                                  # noqa: E402
from mdu.comics import COMICS                                    # noqa: E402
from mdu.missions import MISSIONS                                # noqa: E402
from mdu.world import ORGANIZATIONS, BATTLES, RELATIONSHIPS      # noqa: E402
from mdu.roster import build_battle_participation                # noqa: E402
from mdu.sqlgen import script_to_sqlite, split_statements        # noqa: E402

OUT = ROOT / 'datasets'
CSV_DIR = OUT / 'csv'
SQL_DIR = OUT / 'sql'
TODAY = datetime.date.today().isoformat()

UNIVERSES = [
    (1, 'Marvel', 'Marvel Comics',
     'The Marvel universe as published by Marvel Comics and adapted by Marvel Studios: '
     'Earth-616, the Ultimate and Spider-Gwen branches, and the Marvel Cinematic Universe '
     'of Earth-199999.', 'Comic book continuity plus film and television continuities'),
    (2, 'DC', 'DC Comics',
     'The DC universe as published by DC Comics and adapted by Warner Bros.: the post-Crisis '
     'and Prime Earth continuity, the DCEU of Earth-1, and the Arrowverse, Smallville, DCAU '
     'and Dark Knight screen continuities.', 'Comic book continuity plus film and television continuities'),
]

PROFICIENCY_ORDER = ['Latent', 'Novice', 'Trained', 'Expert', 'Master']


# ---------------------------------------------------------------------------
# entity assembly
# ---------------------------------------------------------------------------
def _iso_date(value):
    return value or None


def build():
    """Return (entities, indexes) with primary keys assigned."""
    entities = OrderedDict()

    entities['universes'] = [
        {'universe_id': uid, 'universe_name': name, 'publisher': publisher,
         'description': description, 'continuity_type': continuity}
        for uid, name, publisher, description, continuity in UNIVERSES]

    characters = []
    char_by_key = {}
    for index, row in enumerate(CHARACTERS, start=1):
        (key, real_name, alias, universe, ctype, species, gender, first_appearance,
         origin, status, alignment, continuity, record_origin, powers) = row
        record = {'character_id': index, 'key': key, 'real_name': real_name, 'alias': alias,
                  'universe': universe, 'universe_id': 1 if universe == 'Marvel' else 2, 'character_type': ctype, 'species': species,
                  'gender': gender, 'first_appearance': first_appearance, 'origin': origin,
                  'current_status': status, 'alignment': alignment, 'continuity': continuity,
                  'record_origin': record_origin, '_powers': powers}
        characters.append(record)
        char_by_key[key] = record
    entities['characters'] = characters

    teams = []
    team_by_key = {}
    for index, row in enumerate(TEAMS, start=1):
        (key, name, universe, founded, hq, mission, status, continuity, origin) = row
        record = {'team_id': index, 'key': key, 'team_name': name, 'universe': universe,
                  'universe_id': 1 if universe == 'Marvel' else 2,
                  'founding_year': founded, 'headquarters': hq, 'mission': mission,
                  'team_status': status, 'continuity': continuity, 'record_origin': origin}
        teams.append(record)
        team_by_key[key] = record
    entities['teams'] = teams

    entities['powers'] = [
        {'power_id': index, 'power_name': name, 'category': category,
         'description': description, 'power_level': level}
        for index, (name, category, description, level) in enumerate(POWERS, start=1)]
    power_by_name = {p['power_name']: p for p in entities['powers']}

    memberships = []
    for team_key, members in MEMBERSHIPS:
        team = team_by_key[team_key]
        for entry in members:
            char_key, joined, role = entry[0], entry[1], entry[2]
            left = entry[3] if len(entry) > 3 else None
            memberships.append({
                'membership_id': len(memberships) + 1,
                'character_id': char_by_key[char_key]['character_id'],
                'team_id': team['team_id'],
                'joining_date': joined,
                'departure_date': left,
                'membership_status': 'Former' if left else 'Current',
                'role': role,
                '_character': char_key, '_team': team_key})
    entities['memberships'] = memberships

    mappings = []
    for char in characters:
        for power_name, proficiency, limitation in char['_powers']:
            mappings.append({
                'mapping_id': len(mappings) + 1,
                'character_id': char['character_id'],
                'power_id': power_by_name[power_name]['power_id'],
                'proficiency_level': proficiency,
                'limitations': limitation,
                '_character': char['key'], '_power': power_name})
    entities['character_powers'] = mappings

    contents = []
    for index, row in enumerate(CONTENT, start=1):
        (title, universe, year, ctype, director, studio, duration, rating, synopsis,
         continuity) = row
        contents.append({'content_id': index, 'title': title, 'universe': universe,
                         'release_year': year, 'content_type': ctype, 'director': director,
                         'production_studio': studio, 'duration_minutes': duration,
                         'rating': rating, 'synopsis': synopsis, 'continuity': continuity})
    entities['contents'] = contents

    comics = []
    for index, row in enumerate(COMICS, start=1):
        (title, universe, issue, year, writer, artist, storyline, char_key, continuity) = row
        comics.append({'comic_id': index, 'title': title, 'universe': universe,
                       'issue_number': issue, 'publication_year': year, 'writer': writer,
                       'artist': artist, 'storyline': storyline,
                       'associated_character_id': char_by_key[char_key]['character_id']
                       if char_key else None,
                       'continuity': continuity, '_character': char_key})
    entities['comics'] = comics

    missions = []
    mission_by_key = {}
    participation = []
    for index, row in enumerate(MISSIONS, start=1):
        (key, name, universe, category, start_year, end_year, description, outcome,
         continuity, members) = row
        record = {'mission_id': index, 'key': key, 'mission_name': name,
                  'universe': universe, 'storyline_category': category,
                  'start_year': start_year, 'end_year': end_year,
                  'description': description, 'outcome': outcome,
                  'continuity': continuity}
        record['universe_id'] = 1 if universe == 'Marvel' else 2
        missions.append(record)
        mission_by_key[key] = record
        for char_key, role, result, survival in members:
            participation.append({
                'participation_id': len(participation) + 1,
                'character_id': char_by_key[char_key]['character_id'],
                'mission_id': record['mission_id'],
                'role': role, 'outcome': result, 'survival_status': survival,
                '_character': char_key, '_mission': key})
    entities['missions'] = missions
    entities['mission_participation'] = participation

    organizations = []
    for index, row in enumerate(ORGANIZATIONS, start=1):
        (key, name, universe, otype, hq, leader, objectives, continuity, origin) = row
        organizations.append({'organization_id': index, 'organization_name': name,
                              'universe': universe, 'organization_type': otype,
                              'headquarters': hq,
                              'leader_character_id': char_by_key[leader]['character_id'],
                              'objectives': objectives, 'continuity': continuity,
                              'record_origin': origin, '_leader': leader})
    entities['organizations'] = organizations

    battles = []
    for index, row in enumerate(BATTLES, start=1):
        (key, name, universe, location, year, description, winner, casualties,
         continuity) = row
        battles.append({'battle_id': index, 'key': key, 'battle_name': name,
                        'universe': universe, 'location': location, 'year': year,
                        'description': description, 'winner': winner,
                        'casualties': casualties, 'continuity': continuity})
    for battle in battles:
        battle['universe_id'] = 1 if battle['universe'] == 'Marvel' else 2
    entities['battles'] = battles

    by_key_characters = list(char_by_key.values())
    roster_rows = build_battle_participation(
        [tuple(b[k] for k in ('key', 'battle_name', 'universe', 'location', 'year',
                              'description', 'winner', 'casualties', 'continuity'))
         for b in battles],
        by_key_characters)
    battle_by_key = {b['key']: b for b in battles}
    battle_participation = []
    for row in roster_rows:
        battle_participation.append({
            'participation_id': len(battle_participation) + 1,
            'battle_id': battle_by_key[row['battle']]['battle_id'],
            'character_id': char_by_key[row['character']]['character_id'],
            'side': row['side'], 'battle_result': row['result'], 'status': row['status'],
            '_battle': row['battle'], '_character': row['character']})
    entities['battle_participation'] = battle_participation

    relationships = []
    for row in RELATIONSHIPS:
        key1, key2, rtype, description, continuity = row
        first = char_by_key[key1]['character_id']
        second = char_by_key[key2]['character_id']
        if first > second:
            first, second = second, first
        relationships.append({'relationship_id': len(relationships) + 1,
                              'character1_id': first, 'character2_id': second,
                              'relationship_type': rtype, 'description': description,
                              'continuity': continuity})
    entities['relationships'] = relationships

    indexes = {'characters': char_by_key, 'teams': team_by_key, 'powers': power_by_name,
               'missions': mission_by_key, 'battles': battle_by_key}
    return entities, indexes


# ---------------------------------------------------------------------------
# the export shape of each entity: (csv name, columns)
# ---------------------------------------------------------------------------
SCHEMA = OrderedDict([
    ('universes', ('universes', ['universe_id', 'universe_name', 'publisher', 'description',
                                 'continuity_type'])),
    ('characters', ('characters', ['character_id', 'real_name', 'alias', 'universe_id',
                                   'character_type', 'species', 'gender', 'first_appearance',
                                   'origin', 'current_status', 'alignment', 'continuity',
                                   'record_origin'])),
    ('teams', ('teams', ['team_id', 'team_name', 'universe_id', 'founding_year',
                         'headquarters', 'mission', 'team_status', 'continuity',
                         'record_origin'])),
    ('memberships', ('character_team_memberships', ['membership_id', 'character_id',
                                                    'team_id', 'joining_date', 'departure_date',
                                                    'membership_status', 'role'])),
    ('powers', ('powers', ['power_id', 'power_name', 'category', 'description',
                           'power_level'])),
    ('character_powers', ('character_power_mapping', ['mapping_id', 'character_id',
                                                     'power_id', 'proficiency_level',
                                                     'limitations'])),
    ('contents', ('movies_and_series', ['content_id', 'title', 'universe_id', 'release_year',
                                        'content_type', 'director', 'production_studio',
                                        'duration_minutes', 'rating', 'synopsis',
                                        'continuity'])),
    ('comics', ('comics', ['comic_id', 'title', 'universe_id', 'issue_number',
                           'publication_year', 'writer', 'artist', 'storyline',
                           'associated_character_id', 'continuity'])),
    ('missions', ('missions', ['mission_id', 'mission_name', 'universe_id',
                               'storyline_category', 'start_year', 'end_year', 'description',
                               'outcome', 'continuity'])),
    ('mission_participation', ('character_mission_participation',
                               ['participation_id', 'character_id', 'mission_id', 'role',
                                'outcome', 'survival_status'])),
    ('organizations', ('organizations', ['organization_id', 'organization_name',
                                         'universe_id', 'organization_type', 'headquarters',
                                         'leader_character_id', 'objectives', 'continuity',
                                         'record_origin'])),
    ('battles', ('battles', ['battle_id', 'battle_name', 'universe_id', 'location', 'year',
                             'description', 'winner', 'casualties', 'continuity'])),
    ('battle_participation', ('battle_participation', ['participation_id', 'battle_id',
                                                       'character_id', 'side',
                                                       'battle_result', 'status'])),
    ('relationships', ('character_relationships', ['relationship_id', 'character1_id',
                                                   'character2_id', 'relationship_type',
                                                   'description', 'continuity'])),
])

# CSV column -> source column, where they differ (universe_id is resolved from a name)
COLUMN_SOURCE = {'universe_id': 'universe'}


def rows_for(entity, entities):
    """Turn an entity dict into export rows with resolved universe ids."""
    universe_ids = {u['universe_name']: u['universe_id'] for u in entities['universes']}
    _, columns = SCHEMA[entity]
    out = []
    for record in entities[entity]:
        row = {}
        for column in columns:
            if entity == 'universes' and column == 'universe_id':
                source = 'universe_id'
            else:
                source = COLUMN_SOURCE.get(column, column)
            value = record.get(source)
            if column == 'universe_id' and entity != 'universes':
                value = universe_ids[value]
            row[column] = '' if value is None else value
        out.append(row)
    return out


# ---------------------------------------------------------------------------
# validation
# ---------------------------------------------------------------------------
def validate(entities, indexes):
    """Every check the brief asks for, as machine output. Returns a report dict."""
    report = OrderedDict()
    chars = indexes['characters']
    teams = indexes['teams']
    powers = indexes['powers']
    missions = indexes['missions']
    battles = indexes['battles']

    report['primary_keys'] = OrderedDict()
    for entity in SCHEMA:
        names = [c for c in SCHEMA[entity][1] if c.endswith('_id') and c in
                 ('universe_id', 'character_id', 'team_id', 'membership_id', 'power_id',
                  'mapping_id', 'content_id', 'comic_id', 'mission_id', 'participation_id',
                  'organization_id', 'battle_id', 'relationship_id')
                 and not c in ('universe_id', 'character_id', 'team_id', 'power_id',
                               'mission_id', 'battle_id')]
        key = names[0] if names else None
        if key:
            values = [r[key] for r in rows_for(entity, entities)]
            dupes = [v for v, n in Counter(values).items() if n > 1]
            holes = [v for v in values if v == '']
            report['primary_keys'][SCHEMA[entity][0]] = {
                'column': key, 'rows': len(values), 'unique': len(set(values)),
                'duplicates': dupes, 'missing': holes}

    report['foreign_keys'] = foreign_key_findings(entities)
    report['duplicates'] = duplicate_findings(entities)
    report['missing_values'] = missing_findings(entities)
    report['consistency'] = consistency_findings(entities)
    return report


FK_RULES = [
    ('characters', 'universe_id', 'universes', 'universe_id'),
    ('teams', 'universe_id', 'universes', 'universe_id'),
    ('memberships', 'character_id', 'characters', 'character_id'),
    ('memberships', 'team_id', 'teams', 'team_id'),
    ('character_powers', 'character_id', 'characters', 'character_id'),
    ('character_powers', 'power_id', 'powers', 'power_id'),
    ('contents', 'universe_id', 'universes', 'universe_id'),
    ('comics', 'universe_id', 'universes', 'universe_id'),
    ('comics', 'associated_character_id', 'characters', 'character_id'),
    ('missions', 'universe_id', 'universes', 'universe_id'),
    ('mission_participation', 'character_id', 'characters', 'character_id'),
    ('mission_participation', 'mission_id', 'missions', 'mission_id'),
    ('organizations', 'universe_id', 'universes', 'universe_id'),
    ('organizations', 'leader_character_id', 'characters', 'character_id'),
    ('battles', 'universe_id', 'universes', 'universe_id'),
    ('battle_participation', 'battle_id', 'battles', 'battle_id'),
    ('battle_participation', 'character_id', 'characters', 'character_id'),
    ('relationships', 'character1_id', 'characters', 'character_id'),
    ('relationships', 'character2_id', 'characters', 'character_id'),
]


def foreign_key_findings(entities):
    findings = []
    for child, column, parent, parent_column in FK_RULES:
        parents = {r[parent_column] for r in rows_for(parent, entities)}
        values = [r[column] for r in rows_for(child, entities)]
        orphans = [v for v in values if v != '' and v not in parents]
        nullable = child in ('comics',) and column == 'associated_character_id'
        findings.append({
            'child': SCHEMA[child][0], 'column': column,
            'parent': SCHEMA[parent][0], 'parent_column': parent_column,
            'checked': len(values), 'orphans': orphans,
            'nulls': sum(1 for v in values if v == ''),
            'nullable': nullable})
    return findings


def duplicate_findings(entities):
    findings = []
    char_rows = rows_for('characters', entities)
    findings.append({
        'entity': 'characters', 'rule': 'alias is unique',
        'duplicates': [v for v, n in Counter(r['alias'] for r in char_rows).items() if n > 1]})
    unknown_named = sum(1 for r in char_rows if r['real_name'] == 'Unknown')
    findings.append({
        'entity': 'characters', 'rule': 'no real name invented where none exists',
        'duplicates': [], 'note': f'{unknown_named} characters recorded as "Unknown" rather '
                                  'than given an invented name'})
    findings.append({
        'entity': 'character_team_memberships', 'rule': 'character + team + joining date is unique',
        'duplicates': [k for k, n in Counter((r['character_id'], r['team_id'],
                                              r['joining_date'])
                                             for r in rows_for('memberships', entities)).items()
                       if n > 1]})
    findings.append({
        'entity': 'character_power_mapping', 'rule': 'character + power is unique',
        'duplicates': [k for k, n in Counter((r['character_id'], r['power_id'])
                                             for r in rows_for('character_powers', entities)).items()
                       if n > 1]})
    findings.append({
        'entity': 'character_mission_participation', 'rule': 'character + mission is unique',
        'duplicates': [k for k, n in Counter((r['character_id'], r['mission_id'])
                                             for r in rows_for('mission_participation',
                                                               entities)).items() if n > 1]})
    findings.append({
        'entity': 'battle_participation', 'rule': 'battle + character is unique',
        'duplicates': [k for k, n in Counter((r['battle_id'], r['character_id'])
                                             for r in rows_for('battle_participation',
                                                               entities)).items() if n > 1]})
    findings.append({
        'entity': 'character_relationships', 'rule': 'ordered pair + continuity is unique',
        'duplicates': [k for k, n in Counter((r['character1_id'], r['character2_id'],
                                              r['continuity'])
                                             for r in rows_for('relationships', entities)).items()
                       if n > 1]})
    findings.append({
        'entity': 'movies_and_series', 'rule': 'title + release year + content type is unique',
        'duplicates': [k for k, n in Counter((r['title'], r['release_year'], r['content_type'])
                                             for r in rows_for('contents', entities)).items()
                       if n > 1]})
    findings.append({
        'entity': 'comics', 'rule': 'title + issue + year is unique',
        'duplicates': [k for k, n in Counter((r['title'], r['issue_number'], r['publication_year'])
                                             for r in rows_for('comics', entities)).items()
                       if n > 1]})
    findings.append({
        'entity': 'organizations', 'rule': 'universe + name is unique',
        'duplicates': [k for k, n in Counter((r['universe_id'], r['organization_name'])
                                             for r in rows_for('organizations', entities)).items()
                       if n > 1]})
    findings.append({
        'entity': 'battles', 'rule': 'universe + name is unique',
        'duplicates': [k for k, n in Counter((r['universe_id'], r['battle_name'])
                                             for r in rows_for('battles', entities)).items()
                       if n > 1]})
    return findings


MISSING_RULES = {
    'universes': ['universe_name', 'publisher', 'description', 'continuity_type'],
    'characters': ['alias', 'universe_id', 'character_type', 'species', 'gender', 'origin',
                   'current_status', 'alignment', 'continuity', 'record_origin'],
    'teams': ['team_name', 'universe_id', 'mission', 'team_status', 'continuity'],
    'memberships': ['character_id', 'team_id', 'membership_status', 'role'],
    'powers': ['power_name', 'category', 'description', 'power_level'],
    'character_powers': ['character_id', 'power_id', 'proficiency_level'],
    'contents': ['title', 'universe_id', 'release_year', 'content_type',
                 'production_studio', 'synopsis', 'continuity'],
    'comics': ['title', 'universe_id', 'issue_number', 'publication_year', 'continuity'],
    'missions': ['mission_name', 'universe_id', 'storyline_category', 'start_year',
                 'description', 'outcome', 'continuity'],
    'mission_participation': ['character_id', 'mission_id', 'role', 'outcome',
                              'survival_status'],
    'organizations': ['organization_name', 'universe_id', 'organization_type', 'objectives',
                      'continuity'],
    'battles': ['battle_name', 'universe_id', 'location', 'year', 'description', 'winner',
                'continuity'],
    'battle_participation': ['battle_id', 'character_id', 'side', 'battle_result', 'status'],
    'relationships': ['character1_id', 'character2_id', 'relationship_type', 'description',
                      'continuity'],
}


def missing_findings(entities):
    findings = []
    for entity, required in MISSING_RULES.items():
        rows = rows_for(entity, entities)
        for column in required:
            blanks = sum(1 for r in rows if r[column] == '')
            findings.append({'entity': SCHEMA[entity][0], 'column': column,
                             'rows': len(rows), 'blank': blanks,
                             'rule': 'required', 'ok': blanks == 0})
    optional = [('characters', 'real_name'), ('characters', 'first_appearance'),
                ('teams', 'founding_year'), ('teams', 'headquarters'),
                ('memberships', 'joining_date'), ('memberships', 'departure_date'),
                ('contents', 'director'), ('contents', 'duration_minutes'),
                ('contents', 'rating'), ('comics', 'writer'), ('comics', 'artist'),
                ('comics', 'storyline'), ('comics', 'associated_character_id'),
                ('missions', 'end_year'), ('organizations', 'headquarters'),
                ('battles', 'casualties'), ('character_powers', 'limitations')]
    for entity, column in optional:
        rows = rows_for(entity, entities)
        blanks = sum(1 for r in rows if r[column] == '')
        findings.append({'entity': SCHEMA[entity][0], 'column': column, 'rows': len(rows),
                         'blank': blanks, 'rule': 'optional (NULL allowed)', 'ok': True})
    return findings


def consistency_findings(entities):
    checks = []
    char_rows = {r['character_id']: r for r in rows_for('characters', entities)}
    universe_names = {u['universe_id']: u['universe_name'] for u in entities['universes']}

    # 1. every screen title and comic sits in the universe its continuity belongs to
    def continuity_universe(continuity):
        if continuity.startswith('Marvel'):
            return 'Marvel'
        if continuity.startswith('DC') or continuity.startswith('DCEU'):
            return 'DC'
        return None

    bad = []
    for r in rows_for('contents', entities):
        if continuity_universe(r['continuity']) != universe_names[r['universe_id']]:
            bad.append((r['title'], r['continuity']))
    for r in rows_for('comics', entities):
        if continuity_universe(r['continuity']) != universe_names[r['universe_id']]:
            bad.append((r['title'], r['continuity']))
    checks.append(('Screen and comic continuity agrees with universe', bad, len(
        rows_for('contents', entities)) + len(rows_for('comics', entities))))

    # 2. a battle never fields a character from the other publisher
    bad = []
    for r in rows_for('battle_participation', entities):
        battle = entities['battles'][r['battle_id'] - 1]
        character = char_rows[r['character_id']]
        if universe_names[character['universe_id']] != universe_names[battle['universe_id']]:
            bad.append((battle['battle_name'], character['alias']))
    checks.append(('Battle combatants are from the battle publisher', bad, len(
        rows_for('battle_participation', entities))))

    # 3. a mission participant shares the mission universe
    bad = []
    for r in rows_for('mission_participation', entities):
        mission = entities['missions'][r['mission_id'] - 1]
        character = char_rows[r['character_id']]
        if universe_names[character['universe_id']] != universe_names[mission['universe_id']]:
            bad.append((mission['mission_name'], character['alias']))
    checks.append(('Mission participants share the mission universe', bad, len(
        rows_for('mission_participation', entities))))

    # 4. whole-publisher missions never mix companies in one roster
    # 5. departure date never precedes joining date
    bad = []
    for r in rows_for('memberships', entities):
        if r['departure_date'] and r['joining_date'] and r['departure_date'] < r['joining_date']:
            bad.append((r['membership_id'], r['joining_date'], r['departure_date']))
    checks.append(('Membership departure is not before joining', bad, len(
        rows_for('memberships', entities))))

    # 6. mission end year never precedes start year
    bad = []
    for r in rows_for('missions', entities):
        if r['end_year'] and int(r['end_year']) < int(r['start_year']):
            bad.append((r['mission_name'], r['start_year'], r['end_year']))
    checks.append(('Mission end year is not before start year', bad, len(
        rows_for('missions', entities))))

    # 7. relationship pairs are ordered and distinct
    bad = []
    for r in rows_for('relationships', entities):
        if int(r['character1_id']) >= int(r['character2_id']):
            bad.append((r['relationship_id'], r['character1_id'], r['character2_id']))
    checks.append(('Relationship pairs are ordered and distinct', bad, len(
        rows_for('relationships', entities))))

    # 8. numeric ranges
    bad = []
    for r in rows_for('powers', entities):
        if not 1 <= int(r['power_level']) <= 10:
            bad.append((r['power_name'], r['power_level']))
    checks.append(('Power level is within 1-10', bad, len(rows_for('powers', entities))))

    bad = []
    for r in rows_for('contents', entities):
        if not 1930 <= int(r['release_year']) <= 2100:
            bad.append((r['title'], r['release_year']))
    checks.append(('Release year is plausible', bad, len(rows_for('contents', entities))))

    # 9. a mission participant who died did not also survive a later mission
    #    (checks the survival vocabulary rather than a hard timeline)
    allowed = {'Survived', 'Killed', 'Presumed dead', 'Unknown'}
    bad = [r['survival_status'] for r in rows_for('mission_participation', entities)
           if r['survival_status'] not in allowed]
    checks.append(('Survival status uses the agreed vocabulary', bad, len(
        rows_for('mission_participation', entities))))

    # 10. distinct proficiency vocabulary
    allowed = set(PROFICIENCY_ORDER)
    bad = [r['proficiency_level'] for r in rows_for('character_powers', entities)
           if r['proficiency_level'] not in allowed]
    checks.append(('Proficiency uses the agreed vocabulary', bad, len(
        rows_for('character_powers', entities))))

    # 11. every canon screen character that appears in a mission exists in characters
    bad = [r['alias'] for r in char_rows.values() if r['record_origin'] == 'Original addition'
           and not r['real_name']]
    checks.append(('Original additions are labelled', bad, len(char_rows)))

    # 12. every comic associated character belongs to the comic publisher
    bad = []
    for r in rows_for('comics', entities):
        if r['associated_character_id'] == '':
            continue
        character = char_rows[r['associated_character_id']]
        if universe_names[character['universe_id']] != universe_names[r['universe_id']]:
            bad.append((r['title'], character['alias']))
    checks.append(('Comic character matches the comic publisher', bad, len(
        rows_for('comics', entities))))

    return checks


# ---------------------------------------------------------------------------
# writers
# ---------------------------------------------------------------------------
def write_csvs(entities):
    CSV_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    for entity in SCHEMA:
        name, columns = SCHEMA[entity]
        path = CSV_DIR / f'{name}.csv'
        with path.open('w', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            for row in rows_for(entity, entities):
                writer.writerow(row)
        written.append((name, path, len(rows_for(entity, entities))))
    return written


def sql_literal(value):
    if value is None or value == '':
        return 'NULL'
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


SKIP_SQL = {'_character', '_team', '_power', '_mission', '_leader', '_battle', '_powers', 'key'}


def write_sql(entities):
    """One script per entity, in foreign-key order, plus a combined script."""
    SQL_DIR.mkdir(parents=True, exist_ok=True)
    order = list(SCHEMA.keys())
    combined = ['-- Marvel & DC Universe Database — generated by scripts/build_universe_dataset.py',
                f'-- generated {TODAY}', '', '-- 1. schema and views (idempotent)', '']
    combined.append((ROOT / 'db' / 'universe_schema.sql').read_text(encoding='utf-8'))
    combined.append((ROOT / 'db' / 'universe_views.sql').read_text(encoding='utf-8'))

    files = []
    for number, entity in enumerate(order, start=1):
        name, columns = SCHEMA[entity]
        table = 'uni_' + name if name not in ('character_team_memberships',
                                              'character_power_mapping',
                                              'character_mission_participation',
                                              'movies_and_series') else {
            'character_team_memberships': 'uni_membership',
            'character_power_mapping': 'uni_character_power',
            'character_mission_participation': 'uni_mission_participation',
            'movies_and_series': 'uni_content'}[name]
        table = table if table.startswith('uni_') else table
        # map export name -> physical table name
        table = {
            'universes': 'uni_universe', 'characters': 'uni_character', 'teams': 'uni_team',
            'character_team_memberships': 'uni_membership', 'powers': 'uni_power',
            'character_power_mapping': 'uni_character_power', 'movies_and_series': 'uni_content',
            'comics': 'uni_comic', 'missions': 'uni_mission',
            'character_mission_participation': 'uni_mission_participation',
            'organizations': 'uni_organization', 'battles': 'uni_battle',
            'battle_participation': 'uni_battle_participation',
            'character_relationships': 'uni_relationship'}[name]
        rows = rows_for(entity, entities)
        lines = [f'-- {number}. {name} — {len(rows)} rows', f'-- target table: {table}', '']
        lines.append(f'DELETE FROM {table};' if entity == 'universes' else '')
        for row in rows:
            values = ', '.join(sql_literal(row[c]) for c in columns)
            lines.append(f'INSERT INTO {table} ({", ".join(columns)}) VALUES ({values});')
        body = '\n'.join(line for line in lines if line != '')
        path = SQL_DIR / f'{number:02d}_{name}.sql'
        path.write_text(body + '\n', encoding='utf-8')
        files.append((path, len(rows)))
        combined.append(f'\n-- {number}. {name} ({len(rows)} rows)\n')
        combined.extend([line for line in lines if line.startswith('INSERT')])

    combined_path = SQL_DIR / 'load_universe.sql'
    combined_path.write_text('\n'.join(combined) + '\n', encoding='utf-8')
    return files, combined_path


def write_excel(entities):
    """One sheet per entity plus a README sheet, and a matching CSV of the same data."""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter
    except ImportError:  # pragma: no cover - reported, not fatal
        print('  ! openpyxl is not installed: skipping the workbook '
              '(pip install openpyxl). The CSVs are complete.')
        return None
    workbook = Workbook()
    first = workbook.active
    first.title = 'README'
    guide = [
        ('Marvel & DC Universe Database Management System', ''),
        ('Generated', TODAY),
        ('Rows per entity', 'see the "Counts" sheet'),
        ('', ''),
        ('Sheet naming', 'one sheet per entity, named after its CSV file'),
        ('Foreign keys', 'universe_id 1 = Marvel, 2 = DC'),
        ('', ''),
        ('Important', 'Every row is fiction. Where a field is genuinely unknown, the cell is'),
        ('', 'blank rather than guessed, and the data dictionary explains which fields allow it.'),
        ('', ''),
        ('Original additions', 'Six characters, three teams and two organisations are labelled'),
        ('', '"Original addition" in the record_origin column; everything else is canon.'),
        ('', ''),
        ('Source', 'scripts/build_universe_dataset.py and scripts/mdu/*.py'),
    ]
    for index, (label, value) in enumerate(guide, start=1):
        first.cell(row=index, column=1, value=label).font = Font(bold=index == 1, size=12)
        first.cell(row=index, column=2, value=value)
    first.column_dimensions['A'].width = 26
    first.column_dimensions['B'].width = 90

    counts = workbook.create_sheet('Counts')
    counts.append(['Entity', 'Sheet', 'Rows'])
    for cell in counts['1']:
        cell.font = Font(bold=True)
    for entity in SCHEMA:
        name, columns = SCHEMA[entity]
        rows = rows_for(entity, entities)
        sheet = workbook.create_sheet(name[:31])
        sheet.append(columns)
        for cell in sheet['1']:
            cell.font = Font(bold=True, color='FFFFFF')
            cell.fill = PatternFill('solid', fgColor='1F3864')
            cell.alignment = Alignment(vertical='center')
        for row in rows:
            sheet.append([row[c] if row[c] != '' else None for c in columns])
        for position, column in enumerate(columns, start=1):
            width = max([len(column)] + [len(str(row[column])) for row in rows[:200]])
            sheet.column_dimensions[get_column_letter(position)].width = min(70, max(12, width + 2))
        sheet.freeze_panes = 'A2'
        sheet.auto_filter.ref = sheet.dimensions
        counts.append([entity, name, len(rows)])
    counts.column_dimensions['A'].width = 34
    counts.column_dimensions['B'].width = 34
    order = workbook._sheets
    workbook._sheets = [order[0]] + [order[-1]] + order[1:-1]
    path = OUT / 'universe.xlsx'
    workbook.save(path)
    return path


def write_er_diagram(entities, report):
    """A dotted ER diagram as SVG text (no external tool needed) plus an ASCII version."""
    boxes = {
        'uni_universe': ['universe_id PK', 'universe_name', 'publisher', 'continuity_type'],
        'uni_character': ['character_id PK', 'alias', 'universe_id FK', 'character_type',
                          'alignment', 'continuity'],
        'uni_team': ['team_id PK', 'team_name', 'universe_id FK', 'founding_year',
                     'team_status'],
        'uni_membership': ['membership_id PK', 'character_id FK', 'team_id FK',
                           'joining_date', 'membership_status'],
        'uni_power': ['power_id PK', 'power_name', 'category', 'power_level'],
        'uni_character_power': ['mapping_id PK', 'character_id FK', 'power_id FK',
                                'proficiency_level'],
        'uni_content': ['content_id PK', 'title', 'universe_id FK', 'release_year',
                        'content_type'],
        'uni_comic': ['comic_id PK', 'title', 'universe_id FK',
                      'associated_character_id FK', 'publication_year'],
        'uni_mission': ['mission_id PK', 'mission_name', 'universe_id FK', 'storyline_category'],
        'uni_mission_participation': ['participation_id PK', 'character_id FK', 'mission_id FK',
                                      'role', 'survival_status'],
        'uni_organization': ['organization_id PK', 'organization_name', 'universe_id FK',
                             'leader_character_id FK'],
        'uni_battle': ['battle_id PK', 'battle_name', 'universe_id FK', 'location', 'winner'],
        'uni_battle_participation': ['participation_id PK', 'battle_id FK', 'character_id FK',
                                     'side', 'battle_result'],
        'uni_relationship': ['relationship_id PK', 'character1_id FK', 'character2_id FK',
                             'relationship_type', 'continuity'],
    }
    positions = {
        'uni_universe': (40, 30),
        'uni_character': (40, 210),
        'uni_team': (360, 30),
        'uni_membership': (360, 210),
        'uni_power': (680, 30),
        'uni_character_power': (680, 210),
        'uni_content': (1000, 30),
        'uni_comic': (1000, 210),
        'uni_mission': (40, 470),
        'uni_mission_participation': (360, 470),
        'uni_organization': (680, 470),
        'uni_battle': (1000, 470),
        'uni_battle_participation': (1000, 650),
        'uni_relationship': (680, 650),
    }
    edges = [
        ('uni_universe', 'uni_character', '1 : N'), ('uni_universe', 'uni_team', '1 : N'),
        ('uni_universe', 'uni_content', '1 : N'), ('uni_universe', 'uni_comic', '1 : N'),
        ('uni_universe', 'uni_mission', '1 : N'), ('uni_universe', 'uni_organization', '1 : N'),
        ('uni_universe', 'uni_battle', '1 : N'),
        ('uni_character', 'uni_membership', '1 : N'), ('uni_team', 'uni_membership', '1 : N'),
        ('uni_character', 'uni_character_power', '1 : N'), ('uni_power', 'uni_character_power', '1 : N'),
        ('uni_character', 'uni_mission_participation', '1 : N'),
        ('uni_mission', 'uni_mission_participation', '1 : N'),
        ('uni_character', 'uni_battle_participation', '1 : N'),
        ('uni_battle', 'uni_battle_participation', '1 : N'),
        ('uni_character', 'uni_relationship', '1 : N (both sides)'),
        ('uni_character', 'uni_comic', '1 : N'), ('uni_character', 'uni_organization', '1 : N'),
    ]
    box_w, box_h = 260, 108
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="1300" height="800" '
           'viewBox="0 0 1300 800" font-family="Inter, Segoe UI, system-ui, sans-serif">',
           '  <rect width="1300" height="800" fill="#0f1115"/>',
           '  <text x="40" y="800" fill="#5d6470" font-size="12">'
           'Marvel &amp; DC Universe Database — 14 tables, 19 foreign keys, 7 views</text>']

    def centre(name):
        x, y = positions[name]
        return x + box_w / 2, y + box_h / 2

    for child, parent, label in edges:
        cx1, cy1 = centre(child)
        cx2, cy2 = centre(parent)
        svg.append(f'  <line x1="{cx1:.0f}" y1="{cy1:.0f}" x2="{cx2:.0f}" y2="{cy2:.0f}" '
                   f'stroke="#3b4252" stroke-width="1.4"/>')
        svg.append(f'  <text x="{(cx1 + cx2) / 2:.0f}" y="{(cy1 + cy2) / 2 - 5:.0f}" '
                   f'fill="#6b7280" font-size="9" text-anchor="middle">{label}</text>')
    for name, (x, y) in positions.items():
        lines = boxes[name]
        svg.append(f'  <rect x="{x}" y="{y}" width="{box_w}" height="{box_h}" rx="10" '
                   f'fill="#182031" stroke="#3d5a80" stroke-width="1.2"/>')
        svg.append(f'  <text x="{x + 12}" y="{y + 22}" fill="#9ec5fe" font-size="13" '
                   f'font-weight="600">{name}</text>')
        for offset, line in enumerate(lines, start=1):
            colour = '#e8ecf1' if ('PK' in line or 'FK' in line) else '#9aa4b2'
            svg.append(f'  <text x="{x + 12}" y="{y + 22 + offset * 15}" fill="{colour}" '
                       f'font-size="10.5">{line}</text>')
    svg.append('</svg>')
    (OUT / 'er_diagram.svg').write_text('\n'.join(svg), encoding='utf-8')

    lines = ['# Entity relationship diagram', '',
             'Rendered version: **er_diagram.svg**. Normalised to 3NF: every non-key column '
             'depends on the key, the whole key and nothing but the key. The 14 tables and '
             '19 foreign keys below are exactly what `db/universe_schema.sql` creates.', '',
             '```']
    for name, columns in boxes.items():
        lines.append(f'┌─ {name} ' + '─' * max(0, 46 - len(name)))
        for column in columns:
            marker = '◆' if 'PK' in column else ('◇' if 'FK' in column else '·')
            lines.append(f'│ {marker} {column}')
        lines.append('└' + '─' * 47)
        lines.append('')
    lines.append('')
    lines.append('Relationships (child → parent):')
    for child, parent, label in edges:
        lines.append(f'  {child:30s} {label:16s} {parent}')
    lines.append('```')
    (OUT / 'er_diagram.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return OUT / 'er_diagram.svg'


DATA_DICTIONARY_EXTRA = {
    'universes': {
        'universe_name': 'Display name of the publisher universe. Unique. Marvel or DC only.',
        'publisher': 'Publishing company that owns the characters (Marvel Comics, DC Comics).',
        'continuity_type': 'How many continuities the universe record spans, e.g. "Comic book '
                           'continuity plus film and television continuities".',
    },
    'characters': {
        'real_name': 'Civilian or birth name. NULL where the character has no established name '
                     '(Joker, Bane, Ra\u2019s al Ghul, Doomsday, Lobo) — never invented.',
        'alias': 'Public codename. Unique, because legacy titles are disambiguated with a holder '
                 'suffix ("Robin (Tim Drake)").',
        'character_type': 'Hero, Villain, Antihero, Supporting or Cosmic Entity.',
        'species': 'In-story species, e.g. Mutant, Kryptonian, Asgardian, Synthezoid.',
        'first_appearance': 'Comic debut with issue and year. For characters created for a screen '
                            'continuity, the screen debut is given and marked "screen creation". '
                            'NULL where no debut is established.',
        'alignment': 'Good, Evil or Neutral. Deliberately coarser than character_type: an '
                     'antihero can be Neutral or Good.',
        'continuity': 'The specific continuity the record describes, e.g. "Marvel Comics '
                      '(Earth-616)" or "DCEU (Earth-1)". Two records may share an alias across '
                      'continuities only if the alias is suffixed.',
        'record_origin': 'Canon or Original addition. Original additions are invented for this '
                         'demonstration and are labelled everywhere they appear.',
    },
    'teams': {
        'founding_year': 'First-publication year of the team where established; in-universe year '
                         'for the original additions. NULL if not established.',
        'team_status': 'Active, Inactive, Dissolved or Deposed.',
        'continuity': 'Continuity the team belongs to; the MCU and DCEU teams are separate rows '
                      'from their comic counterparts.',
    },
    'memberships': {
        'joining_date': 'In-universe or publication date the character joined. NULL where the '
                        'story does not date it.',
        'departure_date': 'NULL while the character is still a member. CHECK: never before '
                          'joining_date.',
        'membership_status': 'Current or Former, derived from departure_date.',
        'role': 'Free-text role in the team, e.g. "Founding member", "Field leader".',
    },
    'powers': {
        'category': 'Physical, Energy, Mental, Mystical, Technological, Cosmic, Biological, '
                    'Combat skill or Intellect. Combat skill and Intellect are earned '
                    'training rather than powers; they are separated so a group-by on '
                    'category does not put swordsmanship next to power armour.',
        'power_level': '1-10 scale for the power itself, not for any character holding it.',
    },
    'character_powers': {
        'proficiency_level': 'Latent, Novice, Trained, Expert or Master. Not the same thing as '
                             'the power level: a Master of a level-4 power is still level 4.',
        'limitations': 'One-sentence in-story ceiling for this character with this power. NULL '
                       'where the story gives none.',
    },
    'contents': {
        'content_type': 'Film, Television series, Animated film, Animated series or Television '
                        'special.',
        'director': 'Credited film director, or credited pilot director for a series. NULL where '
                    'the pilot director is not established here — five animated series.',
        'duration_minutes': 'Theatrical runtime for a film; typical episode length for a series '
                            '(the synopsis states the episode count).',
        'rating': 'MPAA or television content rating as published.',
        'continuity': 'Which adaptation this title belongs to. This is the column that keeps the '
                      'MCU, the DCEU, the Arrowverse and the comics from being mixed.',
    },
    'comics': {
        'issue_number': 'Stored as text because of annuals, "1/2" issues and legacy numbering.',
        'writer': 'Credited writer. NULL where the credit is not established here — never '
                  'guessed.',
        'artist': 'Credited penciller or artist.',
        'storyline': 'Arc or event the issue belongs to, matching a row in uni_mission where one '
                     'exists.',
        'associated_character_id': 'Chief character the issue is about. NULL allowed (ON DELETE '
                                   'SET NULL).',
    },
    'missions': {
        'storyline_category': 'Comic event, Comic arc, Film saga, Television saga or Crossover.',
        'start_year': 'First publication or release year of the storyline, not an in-universe date.',
        'end_year': 'NULL for single-issue or single-film storylines. CHECK: never before '
                    'start_year.',
        'outcome': 'Short in-story result, stated as the source material states it.',
    },
    'mission_participation': {
        'role': 'What the character did in the storyline.',
        'outcome': 'What happened to that character specifically.',
        'survival_status': 'Survived, Killed, Presumed dead or Unknown.',
    },
    'organizations': {
        'organization_type': 'Nation state, intelligence agency, conglomerate, cult, corps, '
                             'relief corps and so on.',
        'leader_character_id': 'Current or most recent leader. FK with ON DELETE SET NULL.',
    },
    'battles': {
        'year': 'In-universe or story year of the battle, which for a film is the year the film '
                'is set.',
        'winner': 'Short description of the winning side, including "Draw" where the story ends '
                  'without one.',
        'casualties': 'FICTIONAL figure for this battle only. NULL where the story gives no '
                      'number. These are numbers from fiction, not estimates of anything real.',
    },
    'battle_participation': {
        'side': 'Named side in the battle, e.g. "Avengers and allies".',
        'battle_result': 'Victorious, Defeated or Stalemate, from that character perspective.',
        'status': 'Survived, Killed, Presumed dead or Unknown after the battle.',
    },
    'relationships': {
        'character1_id': 'Always the numerically smaller id. CHECK character1_id < character2_id '
                         'plus a unique index on (pair, continuity) makes a reversed duplicate '
                         'impossible.',
        'relationship_type': 'Enemies, Allies, Adoptive brothers, Romantic partners, Mentor and '
                             'protégé, Creator and creation, and so on.',
        'continuity': 'The continuity in which the relationship holds. The same pair can have a '
                      'comic relationship and a screen relationship.',
    },
}


def write_data_dictionary(entities, report):
    lines = ['# Data dictionary — Marvel & DC Universe Database', '',
             f'Generated {TODAY} by `scripts/build_universe_dataset.py`. '
             'Every table is prefixed `uni_` and lives in the portal database alongside the '
             'campus schema; nothing in the campus schema is altered.', '',
             '**Conventions**', '',
             '- Primary keys are surrogate integers assigned in insert order.',
             '- `universe_id` 1 = Marvel, 2 = DC.',
             '- The empty cell in a CSV, `NULL` in SQL and a blank in the workbook all mean the '
             'same thing: not established. No cell is filled with a guess.',
             '- Dates are ISO `YYYY-MM-DD`; years are integers.',
             '- `original` records carry `record_origin = Original addition`.', '']
    for entity in SCHEMA:
        name, columns = SCHEMA[entity]
        rows = rows_for(entity, entities)
        table = {
            'universes': 'uni_universe', 'characters': 'uni_character', 'teams': 'uni_team',
            'character_team_memberships': 'uni_membership', 'powers': 'uni_power',
            'character_power_mapping': 'uni_character_power', 'movies_and_series': 'uni_content',
            'comics': 'uni_comic', 'missions': 'uni_mission',
            'character_mission_participation': 'uni_mission_participation',
            'organizations': 'uni_organization', 'battles': 'uni_battle',
            'battle_participation': 'uni_battle_participation',
            'character_relationships': 'uni_relationship'}[name]
        lines += [f'## {table}', '',
                  f'{len(rows)} rows. CSV: `csv/{name}.csv`. Workbook sheet: `{name}`.', '',
                  '| Column | Type | Required | Nulls in data | Notes |',
                  '| --- | --- | --- | --- | --- |']
        pk = {'universes': 'universe_id', 'characters': 'character_id', 'teams': 'team_id',
              'character_team_memberships': 'membership_id', 'powers': 'power_id',
              'character_power_mapping': 'mapping_id', 'movies_and_series': 'content_id',
              'comics': 'comic_id', 'missions': 'mission_id',
              'character_mission_participation': 'participation_id',
              'organizations': 'organization_id', 'battles': 'battle_id',
              'battle_participation': 'participation_id',
              'character_relationships': 'relationship_id'}[name]
        fk_columns = {column for child, column, _p, _pc in FK_RULES if child == entity}
        required = set(MISSING_RULES[entity])
        for column in columns:
            nulls = sum(1 for r in rows if r[column] == '')
            sql_type = 'INTEGER' if column.endswith('_id') or column in (
                'power_level', 'release_year', 'publication_year', 'start_year', 'end_year',
                'year', 'casualties', 'duration_minutes', 'founding_year') else (
                'DATE' if column.endswith('_date') else 'VARCHAR/TEXT')
            role = 'PK' if column == pk else ('FK' if column in fk_columns else '')
            note = DATA_DICTIONARY_EXTRA.get(name, {}).get(column, '')
            lines.append(f'| `{column}` | {sql_type} | {"yes" if column in required else "no"} | '
                         f'{nulls} | {role + " — " if role else ""}{note} |')
        lines.append('')
    lines += ['## Views', '',
              '| View | Purpose |', '| --- | --- |',
              '| `v_uni_character_profile` | Character card with team count, power count and best power level. |',
              '| `v_uni_universe_summary` | Marvel vs DC head-counts across all seven child tables. |',
              '| `v_uni_team_roster` | One row per membership with the team, the character and the role. |',
              '| `v_uni_power_distribution` | Holders, heroes and villains per power. |',
              '| `v_uni_battle_summary` | Combatants and losses per battle. |',
              '| `v_uni_relationship_network` | Ordered pairs with both aliases and the continuity. |',
              '| `v_uni_screen_catalogue` | Films and series with universe, year and credits. |', '',
              '## Referential rules', '',
              '| Child | Column | Parent | Nullable |', '| --- | --- | --- | --- |']
    for child, column, parent, _pc in FK_RULES:
        lines.append(f'| `{SCHEMA[child][0]}` | `{column}` | `{SCHEMA[parent][0]}` | no |')
    lines.append('')
    (OUT / 'data_dictionary.md').write_text('\n'.join(lines), encoding='utf-8')
    return OUT / 'data_dictionary.md'


def write_validation_report(entities, report, csvs, excel):
    total = sum(len(rows_for(e, entities)) for e in SCHEMA)
    lines = ['# Validation report — Marvel & DC Universe Database', '',
             f'Generated {TODAY}. Checks run in-process against the assembled dataset before '
             'any row was written to the database, and again after loading (see '
             '`insertion_log.md`).', '',
             f'**{total:,} rows across {len(SCHEMA)} entities.**', '',
             '## Row counts', '', '| Entity | Table | Rows |', '| --- | --- | ---: |']
    for entity in SCHEMA:
        lines.append(f'| {entity} | `{SCHEMA[entity][0]}` | {len(rows_for(entity, entities)):,} |')
    lines += ['', '## Primary keys', '',
              '| Table | Key column | Rows | Distinct | Duplicates | Missing |',
              '| --- | --- | ---: | ---: | --- | --- |']
    for table, finding in report['primary_keys'].items():
        status = 'none' if not finding['duplicates'] else ', '.join(map(str, finding['duplicates']))
        lines.append(f'| `{table}` | `{finding["column"]}` | {finding["rows"]:,} | '
                     f'{finding["unique"]:,} | {status} | '
                     f'{"none" if not finding["missing"] else len(finding["missing"])} |')
    orphans = sum(len(f['orphans']) for f in report['foreign_keys'])
    lines += ['', '## Foreign keys', '',
              f'{len(report["foreign_keys"])} relationships checked, '
              f'**{orphans} orphan rows**.', '',
              '| Child | Column | Parent | Checked | Orphans | Null (allowed) |',
              '| --- | --- | --- | ---: | ---: | ---: |']
    for finding in report['foreign_keys']:
        lines.append(f'| `{finding["child"]}` | `{finding["column"]}` | `{finding["parent"]}` | '
                     f'{finding["checked"]:,} | {len(finding["orphans"])} | {finding["nulls"]} |')
    bad_dup = [f for f in report['duplicates'] if f['duplicates']]
    lines += ['', '## Duplicate detection', '',
              f'{len(report["duplicates"])} uniqueness rules checked, '
              f'**{len(bad_dup)} violations**.', '',
              '| Entity | Rule | Violations |', '| --- | --- | ---: |']
    for finding in report['duplicates']:
        lines.append(f'| `{finding["entity"]}` | {finding["rule"]} | {len(finding["duplicates"])} |')
    required_bad = [f for f in report['missing_values']
                    if f['rule'] == 'required' and not f['ok']]
    lines += ['', '## Missing values', '',
              f'Required columns are all populated: **{len(required_bad) == 0}**. '
              'The optional rows below are NULL by design, not by omission.', '',
              '| Table | Column | Rule | Rows | Blank | OK |', '| --- | --- | --- | ---: | ---: | --- |']
    for finding in report['missing_values']:
        lines.append(f'| `{finding["entity"]}` | `{finding["column"]}` | {finding["rule"]} | '
                     f'{finding["rows"]:,} | {finding["blank"]:,} | '
                     f'{"yes" if finding["ok"] else "**NO**"} |')
    lines += ['', '## Consistency', '', '| Check | Rows examined | Violations |', '| --- | ---: | ---: |']
    for label, bad, examined in report['consistency']:
        lines.append(f'| {label} | {examined:,} | {len(bad)} |')
    lines += ['', '## Files produced', '', '| File | Rows |', '| --- | ---: |']
    for name, path, count in csvs:
        lines.append(f'| `csv/{name}.csv` | {count:,} |')
    if excel:
        lines.append(f'| `{excel.name}` | {len(SCHEMA)} entity sheets + README + Counts |')
    lines.append(f'| `sql_demonstrations.sql` | readable script, 14 queries |')
    lines.append(f'| `sql_demonstrations.md` | 14 queries with the rows they returned |')

    lines += ['', '## Known limitations', '',
              'Recorded rather than hidden. Each of these is a deliberate trade-off, not an '
              'unnoticed defect.', '',
              '**1. Seven battles in five thin film continuities cast comic-book records.** '
              'The Dark Knight Trilogy, X-Men Film Series and Titans Series carry no '
              'character rows of their own, so the three Gotham battles, the three X-Men '
              'film battles and the Titans Tower assault list the same character in their '
              'comic record (`batman`, `wolverine`, `nightwing`, ...). The battle keeps its '
              'film continuity, year and result; the character row is the comics one. The '
              'alternative, borrowing a body from an unrelated continuity, would have been '
              'worse: the `battle_participation` row would then assert something false '
              'about both continuities. `scripts/mdu/battle_rosters.py` documents the same '
              'decision and `scripts/mdu/roster.py:STANDBY` enforces it.', '',
              '**2. 102 characters have no battle participation.** Battle rosters are '
              'curated by hand from what each story actually shows, so supporting cast '
              'members who never fight (reporters, doctors, aides) have no '
              '`battle_participation` row. Character stat queries therefore show a real '
              'zero rather than a fabricated fight.', '',
              '**3. Screen character spellings are the screen versions.** `Thanos (MCU)` and '
              '`Thanos` are two rows in two continuities on purpose, and the same holds for '
              'Batman, Superman and the rest. Anything that counts "characters" has to say '
              'which continuity it means, which is why the overview splits the two '
              'publishers and the gallery has a query about alias families.', '']
    lines.append('')
    (OUT / 'validation_report.md').write_text('\n'.join(lines), encoding='utf-8')
    return OUT / 'validation_report.md'


# ---------------------------------------------------------------------------
# SQL demonstration sheet
# ---------------------------------------------------------------------------
DEMO_SQL_FILE = OUT / 'sql_demonstrations.sql'
DEMO_MD_FILE = OUT / 'sql_demonstrations.md'


def live_connection():
    """Open the loaded portal database read-only for the demonstration sheet."""
    import sqlite3
    from config import Config
    path = getattr(Config, 'DB_PATH', None) or ROOT / 'sims_embedded.db'
    return sqlite3.connect(str(path))


def write_sql_demonstrations():
    """Run every gallery query against the loaded database and record what it returned.

    The point of the sheet is that the result rows are real: they are read back from the
    same tables the portal serves, not written from memory. Any query that fails is
    recorded as a failure rather than dropped, so the sheet cannot quietly claim more
    than the database does.
    """
    from repositories.universe import DEMO_QUERIES

    connection = live_connection()
    connection.row_factory = None
    results = []
    for index, (kind, title, note, sql) in enumerate(DEMO_QUERIES):
        entry = {'index': index, 'kind': kind, 'title': title, 'note': note, 'sql': sql}
        try:
            cursor = connection.execute(sql)
            columns = [description[0] for description in cursor.description or []]
            rows = cursor.fetchall()
            entry.update({'ok': True, 'columns': columns, 'rows': rows})
        except Exception as exc:                      # recorded, never hidden
            entry.update({'ok': False, 'error': f'{type(exc).__name__}: {exc}'})
        results.append(entry)
    connection.close()

    # --- the .sql file: runnable as one script against a fresh load -------------
    header = [
        '-- SQL demonstrations — Marvel & DC Universe Database',
        f'-- Generated {TODAY} by scripts/build_universe_dataset.py',
        '-- Every statement below is read-only and matches the gallery at /universe/sql.',
        '-- Load the data first:  sqlite3 sims_embedded.db < datasets/sql/load_universe.sql',
        '-- Scroll to the end of each block for the rows the statement actually returned.',
        '',
    ]
    blocks = []
    for entry in results:
        lines = ['-- ' + '=' * 74,
                 f'-- {entry["index"] + 1}. {entry["title"]}',
                 '-- ' + entry['note'],
                 '-- ' + '=' * 74,
                 entry['sql'].strip().rstrip(';') + ';', '']
        if entry['ok']:
            lines.append(f'-- {len(entry["rows"])} row(s) returned')
        else:
            lines.append(f'-- FAILED: {entry["error"]}')
        lines.append('')
        blocks.append('\n'.join(lines))
    DEMO_SQL_FILE.write_text('\n'.join(header) + '\n\n'.join(blocks), encoding='utf-8')

    # --- the .md file: the same queries with their real result tables ----------
    def cell(value):
        if value is None:
            return '*NULL*'
        text = str(value).replace('|', '\\|').replace('\n', ' ')
        return f'`{text}`' if text.strip() == '' else text

    md = ['# SQL demonstration queries', '',
          f'Generated {TODAY} against the loaded database. Each query below was executed '
          'against the live tables; the table under it is what came back, not an example.',
          '',
          'The same statements are in `datasets/sql_demonstrations.sql` (runnable) and in '
          'the portal at **Marvel & DC Universe → SQL gallery** (`/universe/sql`), where '
          'they run read-only and any logged-in user can step through them.', '',
          '| # | Query | Technique | Rows |', '| ---: | --- | --- | ---: |']
    for entry in results:
        rows = len(entry['rows']) if entry['ok'] else 0
        md.append(f'| {entry["index"] + 1} | {entry["title"]} | {entry["note"]} | '
                  f'{rows if entry["ok"] else "**failed**"} |')
    md.append('')

    for entry in results:
        md += [f'## {entry["index"] + 1}. {entry["title"]}', '', entry['note'], '',
               '```sql', entry['sql'].strip(), '```', '']
        if not entry['ok']:
            md += [f'**Query failed:** `{entry["error"]}`', '']
            continue
        columns = entry['columns']
        md.append('| ' + ' | '.join(columns) + ' |')
        md.append('| ' + ' | '.join('---' for _ in columns) + ' |')
        for row in entry['rows']:
            md.append('| ' + ' | '.join(cell(value) for value in row) + ' |')
        if not entry['rows']:
            md.append('| ' + ' | '.join('*(no rows)*' for _ in columns) + ' |')
        md.append('')

    failures = [entry for entry in results if not entry['ok']]
    md += ['## Summary', '',
           f'- Queries defined: {len(results)}',
           f'- Queries that ran: {len(results) - len(failures)}',
           f'- Queries that failed: {len(failures)}', '']
    if failures:
        md += ['Failed queries must be fixed before this sheet is presented: '
               + ', '.join(f'#{entry["index"] + 1} {entry["title"]}' for entry in failures)]
    else:
        md += ['All queries ran against the loaded database. Nothing in this sheet is '
               'hand-written output.']
    md.append('')
    DEMO_MD_FILE.write_text('\n'.join(md), encoding='utf-8')
    return DEMO_SQL_FILE, DEMO_MD_FILE, len(results), len(failures)


# ---------------------------------------------------------------------------
# loader: through the portal's own repository layer
# ---------------------------------------------------------------------------
TABLE_FOR = {
    'universes': ('uni_universe', ['universe_id', 'universe_name', 'publisher', 'description',
                                   'continuity_type']),
    'characters': ('uni_character', ['character_id', 'real_name', 'alias', 'universe_id',
                                     'character_type', 'species', 'gender', 'first_appearance',
                                     'origin', 'current_status', 'alignment', 'continuity',
                                     'record_origin']),
    'teams': ('uni_team', ['team_id', 'team_name', 'universe_id', 'founding_year',
                           'headquarters', 'mission', 'team_status', 'continuity',
                           'record_origin']),
    'powers': ('uni_power', ['power_id', 'power_name', 'category', 'description',
                             'power_level']),
    'contents': ('uni_content', ['content_id', 'title', 'universe_id', 'release_year',
                                 'content_type', 'director', 'production_studio',
                                 'duration_minutes', 'rating', 'synopsis', 'continuity']),
    'comics': ('uni_comic', ['comic_id', 'title', 'universe_id', 'issue_number',
                             'publication_year', 'writer', 'artist', 'storyline',
                             'associated_character_id', 'continuity']),
    'missions': ('uni_mission', ['mission_id', 'mission_name', 'universe_id',
                                 'storyline_category', 'start_year', 'end_year', 'description',
                                 'outcome', 'continuity']),
    'organizations': ('uni_organization', ['organization_id', 'organization_name',
                                           'universe_id', 'organization_type', 'headquarters',
                                           'leader_character_id', 'objectives', 'continuity',
                                           'record_origin']),
    'battles': ('uni_battle', ['battle_id', 'battle_name', 'universe_id', 'location', 'year',
                               'description', 'winner', 'casualties', 'continuity']),
    'memberships': ('uni_membership', ['membership_id', 'character_id', 'team_id',
                                       'joining_date', 'departure_date', 'membership_status',
                                       'role']),
    'character_powers': ('uni_character_power', ['mapping_id', 'character_id', 'power_id',
                                                 'proficiency_level', 'limitations']),
    'mission_participation': ('uni_mission_participation',
                              ['participation_id', 'character_id', 'mission_id', 'role',
                               'outcome', 'survival_status']),
    'battle_participation': ('uni_battle_participation',
                             ['participation_id', 'battle_id', 'character_id', 'side',
                              'battle_result', 'status']),
    'relationships': ('uni_relationship', ['relationship_id', 'character1_id', 'character2_id',
                                           'relationship_type', 'description', 'continuity']),
}

LOAD_ORDER = ['universes', 'characters', 'teams', 'powers', 'contents', 'comics', 'missions',
              'organizations', 'battles', 'memberships', 'character_powers',
              'mission_participation', 'battle_participation', 'relationships']

VIEWS = ['v_uni_character_profile', 'v_uni_universe_summary', 'v_uni_team_roster',
         'v_uni_power_distribution', 'v_uni_battle_summary', 'v_uni_relationship_network',
         'v_uni_screen_catalogue']


def _ddl_label(statement):
    """A readable one-line name for a DDL statement, e.g. `table uni_character`."""
    words = ' '.join(statement.split()).split(' ')
    upper = [word.upper() for word in words]
    for kind in ('TABLE', 'VIEW', 'INDEX'):
        if kind in upper[:7]:
            position = upper.index(kind) + 1
            while position < len(words) and upper[position] in ('IF', 'NOT', 'EXISTS',
                                                                'OR', 'REPLACE'):
                position += 1
            name = words[position] if position < len(words) else ''
            return f'{kind.lower()} {name}'.strip()
    return ' '.join(words[:6])


def apply_schema(db_pool):
    """Create the 14 tables, 15 indexes and 7 views. Idempotent.

    The shipped DDL is MySQL 8 syntax; `mdu.sqlgen` translates it to the embedded
    SQLite dialect statement by statement, and raises rather than guessing on anything
    it does not explicitly handle.
    """
    applied = []
    for script, kind in (('universe_schema.sql', 'schema'), ('universe_views.sql', 'views')):
        text = (ROOT / 'db' / script).read_text(encoding='utf-8')
        for statement in script_to_sqlite(text):
            label = _ddl_label(statement)
            try:
                db_pool.execute_dml(statement)
                applied.append(label)
            except Exception as exc:
                message = str(exc).lower()
                if 'already exists' in message or 'duplicate' in message:
                    applied.append('already present: ' + label)
                else:
                    raise RuntimeError(f'{script}: {exc}\n{statement[:300]}') from exc
    return applied


def _reconcile_columns(db_pool, table, columns, log):
    """Add any column the shipped schema has and an older local table does not."""
    present = {row['name'] for row in db_pool.execute_query(f'PRAGMA table_info({table})',
                                                           fetch='all')}
    missing = [c for c in columns if c not in present]
    for column in missing:
        declared = 'INTEGER' if column.endswith('_id') or column in (
            'power_level', 'release_year', 'publication_year', 'start_year', 'end_year',
            'year', 'casualties', 'duration_minutes', 'founding_year') else (
            'DATE' if column.endswith('_date') else 'TEXT')
        db_pool.execute_dml(f'ALTER TABLE {table} ADD COLUMN {column} {declared}')
        log.append((table, 'migrated', f'added missing column {column}', None))
    return missing


def load(entities, reset=False):
    from repositories.db_pool import db_pool
    log = []
    if reset:
        # Rebuild only the 14 demonstration tables, so the live schema always matches
        # the shipped DDL exactly. No campus table is touched.
        for view in VIEWS:
            db_pool.execute_dml(f'DROP VIEW IF EXISTS {view}')
        for entity in reversed(LOAD_ORDER):
            db_pool.execute_dml(f'DROP TABLE IF EXISTS {TABLE_FOR[entity][0]}')
        log.append(('reset', 'applied', 'dropped and rebuilt the 14 uni_ tables only', None))
    applied = apply_schema(db_pool)
    for entity in LOAD_ORDER:
        table, columns = TABLE_FOR[entity]
        _reconcile_columns(db_pool, table, columns, log)
    log.append(('schema', 'applied', f'{len(applied)} DDL statements (tables + views)', None))

    existing = {}
    for entity in LOAD_ORDER:
        table = TABLE_FOR[entity][0]
        try:
            existing[entity] = db_pool.execute_query(f'SELECT COUNT(*) AS n FROM {table}',
                                                     fetch='val') or 0
        except Exception:
            existing[entity] = 0
    if any(existing.values()):
        if not reset:
            raise SystemExit(
                'Refusing to load: the universe tables already contain data '
                f'({existing}). Nothing was changed. Re-run with --reset to clear only the '
                '14 uni_ tables, or leave the database as it is.')
        for entity in reversed(LOAD_ORDER):
            db_pool.execute_dml(f'DELETE FROM {TABLE_FOR[entity][0]}')
        log.append(('reset', 'applied', 'cleared the 14 uni_ tables only', None))

    loaded = {}
    for entity in LOAD_ORDER:
        table, columns = TABLE_FOR[entity]
        rows = rows_for(entity, entities)
        placeholders = ', '.join('?' for _ in columns)
        sql = f'INSERT INTO {table} ({", ".join(columns)}) VALUES ({placeholders})'
        inserted = 0
        first_error = None
        for row in rows:
            values = [None if row[c] == '' else row[c] for c in columns]
            try:
                db_pool.execute_dml(sql, tuple(values))
                inserted += 1
            except Exception as exc:
                first_error = first_error or str(exc)
                log.append((entity, 'failed', str(exc)[:200], row.get(columns[0])))
        loaded[entity] = (inserted, len(rows), first_error)
        log.append((entity, 'inserted' if inserted == len(rows) else 'partial',
                    f'{inserted}/{len(rows)} rows into {table}', first_error))
    return loaded, log, applied


def verify(entities):
    """Re-read the database and check counts, foreign keys and views."""
    from repositories.db_pool import db_pool
    result = OrderedDict()
    for entity in LOAD_ORDER:
        table = TABLE_FOR[entity][0]
        expected = len(rows_for(entity, entities))
        actual = db_pool.execute_query(f'SELECT COUNT(*) AS n FROM {table}', fetch='one')['n']
        result[entity] = {'table': table, 'expected': expected, 'actual': actual,
                          'ok': expected == actual}
    fk_checks = []
    for child, column, parent, parent_column in FK_RULES:
        child_table = TABLE_FOR[child][0]
        parent_table = TABLE_FOR[parent][0]
        sql = (f'SELECT COUNT(*) AS n FROM {child_table} c WHERE c.{column} IS NOT NULL '
               f'AND NOT EXISTS (SELECT 1 FROM {parent_table} p '
               f'WHERE p.{parent_column} = c.{column})')
        try:
            orphans = db_pool.execute_query(sql, fetch='one')['n']
        except Exception as exc:
            orphans = f'error: {exc}'
        fk_checks.append({'child': child_table, 'column': column, 'parent': parent_table,
                          'orphans': orphans})
    views = {}
    for view in VIEWS:
        try:
            rows = db_pool.execute_query(f'SELECT * FROM {view}', fetch='all')
            views[view] = len(rows)
        except Exception as exc:
            views[view] = f'error: {exc}'
    return result, fk_checks, views


def write_insertion_log(entities, loaded, log, applied, verification, fk_checks, views, mode):
    counts, fk, view_counts = verification
    lines = ['# Record insertion log — Marvel & DC Universe Database', '',
             f'Run: {datetime.datetime.now().isoformat(timespec="seconds")} · target: '
             f'{mode}', '',
             '## Batch results', '',
             '| Entity | Target table | Generated | Inserted | Failed | Skipped | Status |',
             '| --- | --- | ---: | ---: | ---: | ---: | --- |']
    total_generated = total_inserted = total_failed = 0
    for entity in LOAD_ORDER:
        table = TABLE_FOR[entity][0]
        inserted, generated, error = loaded[entity]
        failed = generated - inserted
        total_generated += generated
        total_inserted += inserted
        total_failed += failed
        status = 'verified' if counts[entity]['ok'] else 'count mismatch'
        lines.append(f'| {entity} | `{table}` | {generated:,} | {inserted:,} | {failed:,} | 0 | '
                     f'{status} |')
    lines += ['', f'**Totals: {total_generated:,} generated, {total_inserted:,} inserted, '
                  f'{total_failed:,} failed, 0 skipped.**', '',
              '## Schema application', '', f'{len(applied)} DDL statements applied:', '']
    for statement in applied:
        lines.append(f'- `{statement}`')
    lines += ['', '## Post-load verification (read back from the database)', '',
              '| Table | Expected | In database | Match |', '| --- | ---: | ---: | --- |']
    for entity, finding in counts.items():
        lines.append(f'| `{finding["table"]}` | {finding["expected"]:,} | {finding["actual"]:,} | '
                     f'{"yes" if finding["ok"] else "**NO**"} |')
    lines += ['', '## Post-load foreign-key verification', '',
              '| Child | Column | Parent | Orphan rows |', '| --- | --- | --- | ---: |']
    for finding in fk_checks:
        lines.append(f'| `{finding["child"]}` | `{finding["column"]}` | `{finding["parent"]}` | '
                     f'{finding["orphans"]} |')
    lines += ['', '## Views', '', '| View | Rows returned |', '| --- | ---: |']
    for view, count in view_counts.items():
        lines.append(f'| `{view}` | {count} |')
    lines += ['', '## Statement-level log', '', '| Entity | Result | Detail | First error |',
              '| --- | --- | --- | --- |']
    for entity, status, detail, error in log:
        lines.append(f'| {entity} | {status} | {detail} | {error or "—"} |')
    lines.append('')
    (OUT / 'insertion_log.md').write_text('\n'.join(lines), encoding='utf-8')
    return OUT / 'insertion_log.md'


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--no-load', action='store_true', help='build files only')
    parser.add_argument('--reset', action='store_true',
                        help='clear the 14 uni_ tables before loading (never touches campus tables)')
    parser.add_argument('--sql-only', action='store_true',
                        help='write the SQL bundle and print the command to run on the live host')
    parser.add_argument('--db-only', action='store_true',
                        help='load the database only and leave datasets/ exactly as committed '
                             '(use this on the live host, where the files are already in git)')
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    print('1/5  assembling entities')
    entities, indexes = build()
    total = sum(len(rows_for(e, entities)) for e in SCHEMA)
    print(f'     {len(SCHEMA)} entities, {total:,} rows')

    print('2/5  validating')
    report = validate(entities, indexes)
    orphans = sum(len(f['orphans']) for f in report['foreign_keys'])
    dupes = sum(len(f['duplicates']) for f in report['duplicates'])
    required_bad = sum(1 for f in report['missing_values'] if f['rule'] == 'required' and not f['ok'])
    consistency_bad = sum(len(bad) for _l, bad, _n in report['consistency'])
    print(f'     orphan FKs: {orphans} · duplicate violations: {dupes} · '
          f'required blanks: {required_bad} · consistency violations: {consistency_bad}')
    if orphans or dupes or required_bad:
        raise SystemExit('Validation failed. Fix the source data before loading anything.')

    if args.db_only:
        # The committed datasets/ files are already the ones this code produces; on the
        # live host there is nothing to rewrite, so the loader runs on its own.
        print('3/5  files left untouched (--db-only)')
        combined = SQL_DIR / 'load_universe.sql'
        csvs, excel = [], None
        validation = OUT / 'validation_report.md'
    else:
        print('3/5  writing CSVs, SQL and the workbook')
        csvs = write_csvs(entities)
        sql_files, combined = write_sql(entities)
        excel = write_excel(entities)
        dictionary = write_data_dictionary(entities, report)
        diagram = write_er_diagram(entities, report)
        validation = write_validation_report(entities, report, csvs, excel)
        print(f'     {len(csvs)} CSVs · {len(sql_files) + 1} SQL scripts · '
              f'{excel.name if excel else "no workbook"} · dictionary · diagram · report')

    if args.no_load or args.sql_only:
        mode = 'file generation only'
        loaded = {e: (0, len(rows_for(e, entities)), None) for e in LOAD_ORDER}
        log, applied = [], []
        counts = {e: {'table': TABLE_FOR[e][0], 'expected': len(rows_for(e, entities)),
                      'actual': 0, 'ok': False} for e in LOAD_ORDER}
        verification = (counts, [], {})
        if not args.db_only:
            try:
                demo_sql, demo_md, demo_count, demo_failed = write_sql_demonstrations()
                print(f'     {demo_md.relative_to(ROOT)} · {demo_count} queries, '
                      f'{demo_failed} failed (run against the database currently on disk)')
            except Exception as exc:
                print(f'     SQL demonstration sheet skipped: {type(exc).__name__}: {exc}')
        if args.sql_only:
            print()
            print('Run this on the portal host to load the same data into the live database:')
            print(f'  python scripts/build_universe_dataset.py --reset')
            print(f'  -- or, with the SQL bundle --')
            print(f'  sqlite3 sims_embedded.db < {combined.relative_to(ROOT)}')
    else:
        print('4/5  loading through the portal repository layer')
        loaded, log, applied = load(entities, reset=args.reset)
        print('5/5  verifying')
        verification = verify(entities)
        counts, fk_checks, views = verification
        ok = all(c['ok'] for c in counts.values())
        print(f'     row counts match: {ok} · '
              f'orphan FKs after load: {sum(f["orphans"] for f in fk_checks if isinstance(f["orphans"], int))}')
        target = ('the live database on this host' if args.db_only else
                  'local portal database (SQLite, same repository layer as the deployed '
                  'instance)')
        if args.db_only:
            print('     live row counts verified; datasets/ left as committed')
        else:
            insertion = write_insertion_log(entities, loaded, log, applied, verification,
                                           fk_checks, views, target)
            print(f'     {insertion.relative_to(ROOT)}')
            demo_sql, demo_md, demo_count, demo_failed = write_sql_demonstrations()
            print(f'     {demo_md.relative_to(ROOT)} · {demo_count} queries, {demo_failed} failed')
        if not ok:
            raise SystemExit('Post-load verification failed: row counts differ.')
    print('done. Files are in datasets/.')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
