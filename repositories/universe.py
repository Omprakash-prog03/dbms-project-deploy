"""Read models for the Marvel & DC Universe module (the `uni_` tables).

This module is read-only: the dataset is loaded by
`scripts/build_universe_dataset.py`, which is the single writer. Every query here is
plain SQL against the 14 tables and 7 views, so the same statements work on MySQL 8 and
on the embedded engine.
"""
import os
import re
from pathlib import Path

from config import BASE_DIR, Config
from repositories.db_pool import db_pool

DATASET_DIR = Path(BASE_DIR) / 'datasets'

VIEW_NAMES = (
    ('v_uni_character_profile', 'Character card with team and power counts'),
    ('v_uni_universe_summary', 'Marvel vs DC head-counts across every child table'),
    ('v_uni_team_roster', 'One row per membership with team, character and role'),
    ('v_uni_power_distribution', 'Holders, heroes and villains per power'),
    ('v_uni_battle_summary', 'Combatants and losses per battle'),
    ('v_uni_relationship_network', 'Ordered pairs with both aliases'),
    ('v_uni_screen_catalogue', 'Films and series with universe, year and credits'),
)

TABLE_NAMES = (
    ('uni_universe', 'Universe'), ('uni_character', 'Character'), ('uni_team', 'Team'),
    ('uni_membership', 'Character–team membership'), ('uni_power', 'Power'),
    ('uni_character_power', 'Character–power mapping'), ('uni_content', 'Film or series'),
    ('uni_comic', 'Comic issue'), ('uni_mission', 'Mission / storyline'),
    ('uni_mission_participation', 'Character–mission participation'),
    ('uni_organization', 'Organisation'), ('uni_battle', 'Battle'),
    ('uni_battle_participation', 'Battle participation'),
    ('uni_relationship', 'Character relationship'),
)


class MissingDataset(RuntimeError):
    """Raised when the uni_ tables do not exist yet in this database."""


def installed():
    """True when the universe schema has been loaded into this database."""
    try:
        db_pool.execute_query('SELECT 1 FROM uni_universe LIMIT 1', fetch='one')
        return True
    except Exception:
        return False


def _query(sql, params=None, fetch='all'):
    try:
        return db_pool.execute_query(sql, params, fetch=fetch)
    except Exception as exc:
        if 'no such table' in str(exc).lower():
            raise MissingDataset(
                'The Marvel & DC Universe tables are not loaded in this database yet.') from exc
        raise


def _query_flexible(sql, params=None):
    """Try the query as written, then once if the engine lacks a function."""
    try:
        return _query(sql, params)
    except Exception:
        return None


def counts():
    rows = []
    for table, label in TABLE_NAMES:
        try:
            total = db_pool.execute_query(f'SELECT COUNT(*) AS n FROM {table}', fetch='val')
        except Exception:
            raise MissingDataset('The Marvel & DC Universe tables are not loaded yet.')
        rows.append({'table': table, 'label': label, 'rows': total or 0})
    return rows


def overview():
    """Everything the module landing page needs, in a handful of queries."""
    summary = _query('SELECT * FROM v_uni_universe_summary ORDER BY universe_id')
    total_rows = sum(row['rows'] for row in counts())
    alignment = _query("""
        SELECT u.universe_name, c.alignment, COUNT(*) AS n
        FROM uni_character c
        JOIN uni_universe u ON u.universe_id = c.universe_id
        GROUP BY u.universe_name, c.alignment
        ORDER BY u.universe_name, c.alignment""")
    types = _query("""
        SELECT u.universe_name, c.character_type, COUNT(*) AS n
        FROM uni_character c
        JOIN uni_universe u ON u.universe_id = c.universe_id
        GROUP BY u.universe_name, c.character_type
        ORDER BY n DESC""")
    top_powers = _query("""
        SELECT power_name, category, holders, heroes, villains, power_level
        FROM v_uni_power_distribution
        ORDER BY holders DESC, power_name
        LIMIT 8""")
    biggest_teams = _query("""
        SELECT t.team_name, u.universe_name, COUNT(m.membership_id) AS members,
               SUM(CASE WHEN m.membership_status = 'Current' THEN 1 ELSE 0 END) AS current_members
        FROM uni_team t
        JOIN uni_universe u ON u.universe_id = t.universe_id
        LEFT JOIN uni_membership m ON m.team_id = t.team_id
        GROUP BY t.team_id, t.team_name, u.universe_name
        ORDER BY members DESC, t.team_name
        LIMIT 6""")
    lineages = _query("""
        SELECT u.universe_name, COUNT(DISTINCT c.continuity) AS continuities,
               MIN(ct.release_year) AS first_screen_year,
               MAX(ct.release_year) AS latest_screen_year
        FROM uni_character c
        JOIN uni_universe u ON u.universe_id = c.universe_id
        LEFT JOIN uni_content ct ON ct.universe_id = c.universe_id
        GROUP BY u.universe_name
        ORDER BY u.universe_name""")
    costliest = _query("""
        SELECT battle_name, location, year, winner, casualties
        FROM uni_battle
        WHERE casualties IS NOT NULL
        ORDER BY casualties DESC, battle_name
        LIMIT 5""")
    coverage = _query("""
        SELECT c.record_origin, u.universe_name, COUNT(*) AS n
        FROM uni_character c
        JOIN uni_universe u ON u.universe_id = c.universe_id
        GROUP BY c.record_origin, u.universe_name
        ORDER BY c.record_origin, u.universe_name""")
    return {'summary': summary, 'total_rows': total_rows, 'alignment': alignment,
            'types': types, 'top_powers': top_powers, 'biggest_teams': biggest_teams,
            'lineages': lineages, 'costliest': costliest, 'coverage': coverage}


def character_page(args):
    """Filtered, paginated character browser."""
    where, params = [], []
    search = (args.get('search') or '').strip()
    universe = (args.get('universe') or '').strip()
    alignment = (args.get('alignment') or '').strip()
    ctype = (args.get('type') or '').strip()
    continuity = (args.get('continuity') or '').strip()
    if search:
        where.append('(c.alias LIKE %s OR c.real_name LIKE %s OR c.origin LIKE %s)')
        like = f'%{search}%'
        params += [like, like, like]
    if universe:
        where.append('u.universe_name = %s')
        params.append(universe)
    if alignment:
        where.append('c.alignment = %s')
        params.append(alignment)
    if ctype:
        where.append('c.character_type = %s')
        params.append(ctype)
    if continuity:
        where.append('c.continuity = %s')
        params.append(continuity)
    clause = (' WHERE ' + ' AND '.join(where)) if where else ''
    total = _query(f"""
        SELECT COUNT(*) AS n FROM uni_character c
        JOIN uni_universe u ON u.universe_id = c.universe_id{clause}""", tuple(params),
        fetch='one')['n']
    try:
        page = max(1, int(args.get('page') or 1))
    except ValueError:
        page = 1
    per_page = 25
    offset = (page - 1) * per_page
    rows = _query(f"""
        SELECT c.character_id, c.alias, c.real_name, c.character_type, c.species, c.gender,
               c.alignment, c.current_status, c.continuity, c.record_origin, c.first_appearance,
               u.universe_name, u.universe_id,
               (SELECT COUNT(*) FROM uni_membership m WHERE m.character_id = c.character_id) AS teams,
               (SELECT COUNT(*) FROM uni_character_power p WHERE p.character_id = c.character_id) AS powers
        FROM uni_character c
        JOIN uni_universe u ON u.universe_id = c.universe_id{clause}
        ORDER BY u.universe_id, c.alias
        LIMIT {per_page} OFFSET {offset}""", tuple(params))
    facets = {
        'universes': _query('SELECT universe_id, universe_name FROM uni_universe ORDER BY universe_id'),
        'alignments': _query('SELECT DISTINCT alignment FROM uni_character ORDER BY alignment'),
        'types': _query('SELECT DISTINCT character_type FROM uni_character ORDER BY character_type'),
        'continuities': _query('SELECT DISTINCT continuity FROM uni_character ORDER BY continuity'),
    }
    return {'rows': rows, 'total': total, 'page': page, 'per_page': per_page,
            'pages': max(1, (total + per_page - 1) // per_page), 'facets': facets,
            'filters': {'search': search, 'universe': universe, 'alignment': alignment,
                        'type': ctype, 'continuity': continuity}}


def character_detail(character_id):
    character = _query("""
        SELECT c.*, u.universe_name FROM uni_character c
        JOIN uni_universe u ON u.universe_id = c.universe_id
        WHERE c.character_id = %s""", (character_id,), fetch='one')
    if not character:
        return None
    detail = {
        'character': character,
        'teams': _query("""
            SELECT t.team_name, u.universe_name, m.role, m.joining_date, m.departure_date,
                   m.membership_status
            FROM uni_membership m
            JOIN uni_team t ON t.team_id = m.team_id
            JOIN uni_universe u ON u.universe_id = t.universe_id
            WHERE m.character_id = %s
            ORDER BY m.joining_date, t.team_name""", (character_id,)),
        'powers': _query("""
            SELECT p.power_name, p.category, p.power_level, cp.proficiency_level, cp.limitations
            FROM uni_character_power cp
            JOIN uni_power p ON p.power_id = cp.power_id
            WHERE cp.character_id = %s
            ORDER BY p.power_level DESC, p.power_name""", (character_id,)),
        'missions': _query("""
            SELECT m.mission_name, m.storyline_category, m.start_year, m.end_year,
                   mp.role, mp.outcome, mp.survival_status
            FROM uni_mission_participation mp
            JOIN uni_mission m ON m.mission_id = mp.mission_id
            WHERE mp.character_id = %s
            ORDER BY m.start_year""", (character_id,)),
        'battles': _query("""
            SELECT b.battle_name, b.location, b.year, bp.side, bp.battle_result, bp.status,
                   b.winner
            FROM uni_battle_participation bp
            JOIN uni_battle b ON b.battle_id = bp.battle_id
            WHERE bp.character_id = %s
            ORDER BY b.year""", (character_id,)),
        'organizations': _query("""
            SELECT o.organization_name, o.organization_type, o.continuity
            FROM uni_organization o
            WHERE o.leader_character_id = %s
            ORDER BY o.organization_name""", (character_id,)),
        'relationships': _query("""
            SELECT r.relationship_type, r.description, r.continuity,
                   CASE WHEN r.character1_id = %s THEN c2.alias ELSE c1.alias END AS other_alias,
                   CASE WHEN r.character1_id = %s THEN c2.character_id ELSE c1.character_id END
                       AS other_id
            FROM uni_relationship r
            JOIN uni_character c1 ON c1.character_id = r.character1_id
            JOIN uni_character c2 ON c2.character_id = r.character2_id
            WHERE r.character1_id = %s OR r.character2_id = %s
            ORDER BY r.relationship_type""", (character_id, character_id, character_id,
                                              character_id)),
        'comics': _query("""
            SELECT title, issue_number, publication_year, writer, artist, storyline
            FROM uni_comic WHERE associated_character_id = %s
            ORDER BY publication_year""", (character_id,)),
    }
    return detail


def teams_page(args):
    universe = (args.get('universe') or '').strip()
    clause, params = '', []
    if universe:
        clause = ' WHERE u.universe_name = %s'
        params = [universe]
    teams = _query(f"""
        SELECT t.team_id, t.team_name, t.founding_year, t.headquarters, t.mission,
               t.team_status, t.continuity, t.record_origin, u.universe_name,
               COUNT(m.membership_id) AS members,
               SUM(CASE WHEN m.membership_status = 'Current' THEN 1 ELSE 0 END) AS current_members
        FROM uni_team t
        JOIN uni_universe u ON u.universe_id = t.universe_id
        LEFT JOIN uni_membership m ON m.team_id = t.team_id{clause}
        GROUP BY t.team_id, t.team_name, t.founding_year, t.headquarters, t.mission,
                 t.team_status, t.continuity, t.record_origin, u.universe_name
        ORDER BY u.universe_id, members DESC, t.team_name""", tuple(params))
    return {'teams': teams, 'universe': universe}


def team_detail(team_id):
    team = _query("""
        SELECT t.*, u.universe_name FROM uni_team t
        JOIN uni_universe u ON u.universe_id = t.universe_id
        WHERE t.team_id = %s""", (team_id,), fetch='one')
    if not team:
        return None
    members = _query("""
        SELECT c.character_id, c.alias, c.character_type, c.alignment, c.species,
               m.role, m.joining_date, m.departure_date, m.membership_status
        FROM uni_membership m
        JOIN uni_character c ON c.character_id = m.character_id
        WHERE m.team_id = %s
        ORDER BY m.membership_status, m.joining_date, c.alias""", (team_id,))
    return {'team': team, 'members': members}


def powers_page(args):
    category = (args.get('category') or '').strip()
    clause, params = '', []
    if category:
        clause, params = ' WHERE p.category = %s', [category]
    rows = _query(f"""
        SELECT p.power_id, p.power_name, p.category, p.description, p.power_level,
               d.holders, d.heroes, d.villains
        FROM uni_power p
        JOIN v_uni_power_distribution d ON d.power_id = p.power_id{clause}
        ORDER BY p.power_level DESC, d.holders DESC, p.power_name""", tuple(params))
    categories = _query('SELECT DISTINCT category FROM uni_power ORDER BY category')
    return {'powers': rows, 'categories': categories, 'category': category}


def screen_page(args):
    universe = (args.get('universe') or '').strip()
    ctype = (args.get('type') or '').strip()
    continuity = (args.get('continuity') or '').strip()
    where, params = [], []
    if universe:
        where.append('u.universe_name = %s')
        params.append(universe)
    if ctype:
        where.append('ct.content_type = %s')
        params.append(ctype)
    if continuity:
        where.append('ct.continuity = %s')
        params.append(continuity)
    clause = (' WHERE ' + ' AND '.join(where)) if where else ''
    rows = _query(f"""
        SELECT ct.*, u.universe_name FROM uni_content ct
        JOIN uni_universe u ON u.universe_id = ct.universe_id{clause}
        ORDER BY ct.release_year, ct.title""", tuple(params))
    by_year = _query("""
        SELECT release_year, COUNT(*) AS n FROM uni_content
        GROUP BY release_year ORDER BY release_year""")
    return {'rows': rows, 'by_year': by_year,
            'types': _query('SELECT DISTINCT content_type FROM uni_content ORDER BY content_type'),
            'continuities': _query('SELECT DISTINCT continuity FROM uni_content ORDER BY continuity'),
            'filters': {'universe': universe, 'type': ctype, 'continuity': continuity}}


def comics_page(args):
    universe = (args.get('universe') or '').strip()
    clause, params = '', []
    if universe:
        clause = ' WHERE u.universe_name = %s'
        params = [universe]
    rows = _query(f"""
        SELECT cm.comic_id, cm.title, cm.issue_number, cm.publication_year, cm.writer,
               cm.artist, cm.storyline, cm.continuity, u.universe_name, c.alias AS character
        FROM uni_comic cm
        JOIN uni_universe u ON u.universe_id = cm.universe_id
        LEFT JOIN uni_character c ON c.character_id = cm.associated_character_id
        {clause}
        ORDER BY cm.publication_year, cm.title, cm.issue_number""", tuple(params))
    decades = _query("""
        SELECT (publication_year / 10) * 10 AS decade, COUNT(*) AS n
        FROM uni_comic GROUP BY (publication_year / 10) * 10 ORDER BY decade""")
    return {'rows': rows, 'decades': decades, 'universe': universe}


def missions_page(args):
    universe = (args.get('universe') or '').strip()
    clause, params = '', []
    if universe:
        clause = ' WHERE u.universe_name = %s'
        params = [universe]
    rows = _query(f"""
        SELECT m.mission_id, m.mission_name, m.storyline_category, m.start_year, m.end_year,
               m.outcome, m.continuity, u.universe_name,
               (SELECT COUNT(*) FROM uni_mission_participation p
                 WHERE p.mission_id = m.mission_id) AS participants
        FROM uni_mission m
        JOIN uni_universe u ON u.universe_id = m.universe_id{clause}
        ORDER BY m.start_year, m.mission_name""", tuple(params))
    return {'rows': rows, 'universe': universe,
            'categories': _query('SELECT DISTINCT storyline_category FROM uni_mission '
                                 'ORDER BY storyline_category')}


def mission_detail(mission_id):
    mission = _query("""
        SELECT m.*, u.universe_name FROM uni_mission m
        JOIN uni_universe u ON u.universe_id = m.universe_id
        WHERE m.mission_id = %s""", (mission_id,), fetch='one')
    if not mission:
        return None
    participants = _query("""
        SELECT c.character_id, c.alias, c.character_type, c.alignment, p.role, p.outcome,
               p.survival_status
        FROM uni_mission_participation p
        JOIN uni_character c ON c.character_id = p.character_id
        WHERE p.mission_id = %s
        ORDER BY p.survival_status, c.alias""", (mission_id,))
    return {'mission': mission, 'participants': participants}


def organizations_page(args):
    universe = (args.get('universe') or '').strip()
    clause, params = '', []
    if universe:
        clause = ' WHERE u.universe_name = %s'
        params = [universe]
    rows = _query(f"""
        SELECT o.*, u.universe_name, c.alias AS leader,
               (SELECT COUNT(*) FROM uni_organization o2
                 WHERE o2.organization_type = o.organization_type) AS same_type
        FROM uni_organization o
        JOIN uni_universe u ON u.universe_id = o.universe_id
        LEFT JOIN uni_character c ON c.character_id = o.leader_character_id{clause}
        ORDER BY u.universe_id, o.organization_name""", tuple(params))
    return {'rows': rows, 'universe': universe}


def battles_page(args):
    universe = (args.get('universe') or '').strip()
    clause, params = '', []
    if universe:
        clause = ' WHERE u.universe_name = %s'
        params = [universe]
    rows = _query(f"""
        SELECT b.battle_id, b.battle_name, b.location, b.year, b.description, b.winner,
               b.casualties, b.continuity, u.universe_name,
               (SELECT COUNT(*) FROM uni_battle_participation p
                 WHERE p.battle_id = b.battle_id) AS combatants,
               (SELECT COUNT(*) FROM uni_battle_participation p
                 WHERE p.battle_id = b.battle_id AND p.status <> 'Survived') AS losses
        FROM uni_battle b
        JOIN uni_universe u ON u.universe_id = b.universe_id{clause}
        ORDER BY b.year, b.battle_name""", tuple(params))
    return {'rows': rows, 'universe': universe}


def battle_detail(battle_id):
    battle = _query("""
        SELECT b.*, u.universe_name FROM uni_battle b
        JOIN uni_universe u ON u.universe_id = b.universe_id
        WHERE b.battle_id = %s""", (battle_id,), fetch='one')
    if not battle:
        return None
    roster = _query("""
        SELECT c.character_id, c.alias, c.character_type, c.alignment, p.side,
               p.battle_result, p.status
        FROM uni_battle_participation p
        JOIN uni_character c ON c.character_id = p.character_id
        WHERE p.battle_id = %s
        ORDER BY p.side, c.alias""", (battle_id,))
    return {'battle': battle, 'roster': roster}


def relationships_page(args):
    universe = (args.get('universe') or '').strip()
    rtype = (args.get('type') or '').strip()
    where, params = [], []
    if universe:
        where.append('u1.universe_name = %s')
        params.append(universe)
    if rtype:
        where.append('r.relationship_type = %s')
        params.append(rtype)
    clause = (' WHERE ' + ' AND '.join(where)) if where else ''
    rows = _query(f"""
        SELECT r.relationship_id, r.relationship_type, r.description, r.continuity,
               c1.alias AS character_1, c1.character_id AS character_1_id,
               c2.alias AS character_2, c2.character_id AS character_2_id,
               u1.universe_name
        FROM uni_relationship r
        JOIN uni_character c1 ON c1.character_id = r.character1_id
        JOIN uni_character c2 ON c2.character_id = r.character2_id
        JOIN uni_universe u1 ON u1.universe_id = c1.universe_id{clause}
        ORDER BY r.relationship_type, c1.alias""", tuple(params))
    types = _query("""
        SELECT relationship_type, COUNT(*) AS n FROM uni_relationship
        GROUP BY relationship_type ORDER BY n DESC""")
    return {'rows': rows, 'types': types,
            'filters': {'universe': universe, 'type': rtype}}


def membership_page(args):
    where, params = [], []
    universe = (args.get('universe') or '').strip()
    status = (args.get('status') or '').strip()
    if universe:
        where.append('u.universe_name = %s')
        params.append(universe)
    if status:
        where.append('m.membership_status = %s')
        params.append(status)
    clause = (' WHERE ' + ' AND '.join(where)) if where else ''
    rows = _query(f"""
        SELECT m.membership_id, c.alias, c.character_id, t.team_name, t.team_id,
               u.universe_name, m.role, m.joining_date, m.departure_date, m.membership_status
        FROM uni_membership m
        JOIN uni_character c ON c.character_id = m.character_id
        JOIN uni_team t ON t.team_id = m.team_id
        JOIN uni_universe u ON u.universe_id = t.universe_id{clause}
        ORDER BY u.universe_id, t.team_name, m.membership_status, c.alias
        LIMIT 400""", tuple(params))
    return {'rows': rows, 'filters': {'universe': universe, 'status': status}}


# ---------------------------------------------------------------------------
# the SQL demonstration gallery
# ---------------------------------------------------------------------------
DEMO_QUERIES = [
    ('SELECT', 'All Marvel heroes with more than four powers',
     'INNER JOIN + GROUP BY + HAVING. Answers "which Marvel heroes are the most versatile?"',
     """SELECT c.alias, c.character_type, COUNT(cp.power_id) AS powers
FROM uni_character c
JOIN uni_universe u ON u.universe_id = c.universe_id
JOIN uni_character_power cp ON cp.character_id = c.character_id
WHERE u.universe_name = 'Marvel' AND c.alignment = 'Good'
GROUP BY c.character_id, c.alias, c.character_type
HAVING COUNT(cp.power_id) > 4
ORDER BY powers DESC, c.alias"""),

    ('SELECT', 'Universe comparison',
     'Aggregate functions over correlated subqueries: one row per publisher.',
     """SELECT universe_name, characters, teams, screen_titles, comics, missions, battles
FROM v_uni_universe_summary
ORDER BY characters DESC"""),

    ('SELECT', 'Teams with no current members',
     'LEFT JOIN + IS NULL, the classic anti-join.',
     """SELECT t.team_name, u.universe_name, COUNT(m.membership_id) AS ever_members
FROM uni_team t
JOIN uni_universe u ON u.universe_id = t.universe_id
LEFT JOIN uni_membership m ON m.team_id = t.team_id
 AND m.membership_status = 'Current'
WHERE m.membership_id IS NULL
GROUP BY t.team_id, t.team_name, u.universe_name
ORDER BY ever_members DESC"""),

    ('SELECT', 'Character statistics, ranked',
     'Nested query + ORDER BY: the busiest characters across every mapping table.',
     """SELECT c.alias, u.universe_name,
       (SELECT COUNT(*) FROM uni_membership m WHERE m.character_id = c.character_id) AS teams,
       (SELECT COUNT(*) FROM uni_character_power p WHERE p.character_id = c.character_id) AS powers,
       (SELECT COUNT(*) FROM uni_mission_participation q WHERE q.character_id = c.character_id) AS missions,
       (SELECT COUNT(*) FROM uni_battle_participation b WHERE b.character_id = c.character_id) AS battles
FROM uni_character c
JOIN uni_universe u ON u.universe_id = c.universe_id
ORDER BY battles DESC, missions DESC, powers DESC
LIMIT 12"""),

    ('SELECT', 'Power distribution by category',
     'GROUP BY + HAVING + aggregate over a view.',
     """SELECT category, COUNT(*) AS powers, SUM(holders) AS total_holders,
       ROUND(AVG(power_level), 2) AS average_level
FROM v_uni_power_distribution
GROUP BY category
HAVING SUM(holders) > 5
ORDER BY total_holders DESC"""),

    ('SELECT', 'Villains who win battles',
     'Correlated subquery in FROM plus GROUP BY: does evil ever actually win here?',
     """SELECT c.alias AS villain, u.universe_name,
       (SELECT COUNT(*) FROM uni_battle_participation p
         WHERE p.character_id = c.character_id AND p.battle_result = 'Victorious') AS battles_won,
       (SELECT COUNT(*) FROM uni_battle_participation p
         WHERE p.character_id = c.character_id) AS battles_fought
FROM (SELECT character_id FROM uni_character WHERE alignment = 'Evil') evil
JOIN uni_character c ON c.character_id = evil.character_id
JOIN uni_universe u ON u.universe_id = c.universe_id
WHERE battles_won > 0
GROUP BY c.character_id, c.alias, u.universe_name
ORDER BY battles_won DESC, battles_fought DESC, c.alias"""),

    ('SELECT', 'Battles by decade and universe',
     'GROUP BY on a computed expression.',
     """SELECT (year / 10) * 10 AS decade, u.universe_name, COUNT(*) AS battles,
       SUM(CASE WHEN casualties IS NULL THEN 0 ELSE casualties END) AS casualties
FROM uni_battle b
JOIN uni_universe u ON u.universe_id = b.universe_id
GROUP BY (year / 10) * 10, u.universe_name
ORDER BY decade, u.universe_name"""),

    ('SELECT', 'Relationship network density',
     'Self-join on the character table through the relationship table.',
     """SELECT c.alias, COUNT(*) AS relationships
FROM uni_relationship r
JOIN uni_character c ON c.character_id = r.character1_id
GROUP BY c.character_id, c.alias
HAVING COUNT(*) >= 3
ORDER BY relationships DESC"""),

    ('SELECT', 'Screen catalogue by continuity',
     'Distinguishes the adaptations the brief asks to keep separate.',
     """SELECT continuity, content_type, COUNT(*) AS titles,
       MIN(release_year) AS first_year, MAX(release_year) AS last_year
FROM uni_content
GROUP BY continuity, content_type
ORDER BY titles DESC"""),

    ('SELECT', 'Comic decades by publisher',
     'GROUP BY + aggregate on a view-free query.',
     """SELECT (publication_year / 10) * 10 AS decade, u.universe_name, COUNT(*) AS issues
FROM uni_comic cm
JOIN uni_universe u ON u.universe_id = cm.universe_id
GROUP BY (publication_year / 10) * 10, u.universe_name
ORDER BY decade, u.universe_name"""),

    ('SELECT', 'Missions with the heaviest losses',
     'Nested query with a correlated aggregate and a HAVING clause.',
     """SELECT m.mission_name, m.start_year, u.universe_name, COUNT(p.participation_id) AS participants,
       SUM(CASE WHEN p.survival_status = 'Killed' THEN 1 ELSE 0 END) AS killed
FROM uni_mission m
JOIN uni_universe u ON u.universe_id = m.universe_id
JOIN uni_mission_participation p ON p.mission_id = m.mission_id
GROUP BY m.mission_id, m.mission_name, m.start_year, u.universe_name
HAVING SUM(CASE WHEN p.survival_status = 'Killed' THEN 1 ELSE 0 END) > 0
ORDER BY killed DESC, participants DESC"""),

    ('SELECT', 'Characters who lead an organisation',
     'LEFT JOIN from the child side, with a NULL check.',
     """SELECT o.organization_name, o.organization_type, c.alias AS leader,
       c.character_type, u.universe_name
FROM uni_organization o
JOIN uni_universe u ON u.universe_id = o.universe_id
LEFT JOIN uni_character c ON c.character_id = o.leader_character_id
ORDER BY u.universe_name, o.organization_name"""),

    ('SELECT', 'Cross-universe characters (same alias family)',
     'Shows how the comic and screen records are kept apart rather than merged.',
     """SELECT alias, continuity, character_type, current_status
FROM uni_character
WHERE alias LIKE '%(MCU)%' OR alias LIKE '%(DCEU)%'
ORDER BY alias"""),

    ('SELECT', 'Every table, one row count',
     'UNION ALL over literal selects: the row-count ledger for the viva.',
     """SELECT 'uni_universe' AS table_name, COUNT(*) AS rows FROM uni_universe
UNION ALL SELECT 'uni_character', COUNT(*) FROM uni_character
UNION ALL SELECT 'uni_team', COUNT(*) FROM uni_team
UNION ALL SELECT 'uni_membership', COUNT(*) FROM uni_membership
UNION ALL SELECT 'uni_power', COUNT(*) FROM uni_power
UNION ALL SELECT 'uni_character_power', COUNT(*) FROM uni_character_power
UNION ALL SELECT 'uni_content', COUNT(*) FROM uni_content
UNION ALL SELECT 'uni_comic', COUNT(*) FROM uni_comic
UNION ALL SELECT 'uni_mission', COUNT(*) FROM uni_mission
UNION ALL SELECT 'uni_mission_participation', COUNT(*) FROM uni_mission_participation
UNION ALL SELECT 'uni_organization', COUNT(*) FROM uni_organization
UNION ALL SELECT 'uni_battle', COUNT(*) FROM uni_battle
UNION ALL SELECT 'uni_battle_participation', COUNT(*) FROM uni_battle_participation
UNION ALL SELECT 'uni_relationship', COUNT(*) FROM uni_relationship
ORDER BY table_name"""),
]

READ_ONLY = re.compile(r'^\s*(SELECT|WITH)\b', re.I)


def run_demo(index):
    """Run one gallery query. SELECT/WITH only — the gallery is read-only by design."""
    if not 0 <= index < len(DEMO_QUERIES):
        return None
    title, note, sql = DEMO_QUERIES[index][1], DEMO_QUERIES[index][2], DEMO_QUERIES[index][3]
    if not READ_ONLY.match(sql):
        return {'ok': False, 'title': title, 'sql': sql, 'note': note,
                'error': 'The gallery only runs SELECT statements.'}
    try:
        result = _query(sql)
    except MissingDataset as exc:
        return {'ok': False, 'title': title, 'sql': sql, 'note': note, 'error': str(exc)}
    except Exception as exc:
        return {'ok': False, 'title': title, 'sql': sql, 'note': note, 'error': str(exc)}
    columns = list(result[0].keys()) if result else []
    return {'ok': True, 'title': title, 'sql': sql, 'note': note, 'columns': columns,
            'rows': [[row[c] for c in columns] for row in result[:60]],
            'total': len(result)}


# ---------------------------------------------------------------------------
# dataset files, integrity and the verification report
# ---------------------------------------------------------------------------
ARTIFACTS = (
    ('universe.xlsx', 'Excel workbook — one sheet per entity'),
    ('data_dictionary.md', 'Data dictionary — every table and column'),
    ('er_diagram.md', 'ER diagram (text)'),
    ('er_diagram.svg', 'ER diagram (image)'),
    ('validation_report.md', 'Validation report'),
    ('insertion_log.md', 'Record insertion log'),
    ('sql/load_universe.sql', 'Combined SQL load script'),
    ('sql_demonstrations.sql', 'Demonstration queries — runnable script'),
    ('sql_demonstrations.md', 'Demonstration queries with the rows they returned'),
)


def artifacts():
    rows = []
    for name, label in ARTIFACTS:
        path = DATASET_DIR / name
        rows.append({'name': name, 'label': label, 'exists': path.exists(),
                     'bytes': path.stat().st_size if path.exists() else 0})
    csv_dir = DATASET_DIR / 'csv'
    if csv_dir.exists():
        for path in sorted(csv_dir.glob('*.csv')):
            rows.append({'name': f'csv/{path.name}', 'label': 'CSV export',
                         'exists': True, 'bytes': path.stat().st_size})
    return rows


def artifact_path(name):
    """Resolve a whitelisted artifact name to a path inside datasets/."""
    candidate = (DATASET_DIR / name).resolve()
    if not str(candidate).startswith(str(DATASET_DIR.resolve())):
        return None
    if not candidate.is_file():
        return None
    return candidate


def integrity():
    """Live verification: row counts, orphan foreign keys, view health."""
    checks = []
    for child, column, parent, parent_column, table_child, table_parent in (
            ('character', 'universe_id', 'universe', 'universe_id', 'uni_character', 'uni_universe'),
            ('team', 'universe_id', 'universe', 'universe_id', 'uni_team', 'uni_universe'),
            ('membership', 'character_id', 'character', 'character_id', 'uni_membership', 'uni_character'),
            ('membership', 'team_id', 'team', 'team_id', 'uni_membership', 'uni_team'),
            ('character_power', 'character_id', 'character', 'character_id', 'uni_character_power', 'uni_character'),
            ('character_power', 'power_id', 'power', 'power_id', 'uni_character_power', 'uni_power'),
            ('content', 'universe_id', 'universe', 'universe_id', 'uni_content', 'uni_universe'),
            ('comic', 'universe_id', 'universe', 'universe_id', 'uni_comic', 'uni_universe'),
            ('comic', 'associated_character_id', 'character', 'character_id', 'uni_comic', 'uni_character'),
            ('mission', 'universe_id', 'universe', 'universe_id', 'uni_mission', 'uni_universe'),
            ('mission_participation', 'character_id', 'character', 'character_id', 'uni_mission_participation', 'uni_character'),
            ('mission_participation', 'mission_id', 'mission', 'mission_id', 'uni_mission_participation', 'uni_mission'),
            ('organization', 'universe_id', 'universe', 'universe_id', 'uni_organization', 'uni_universe'),
            ('organization', 'leader_character_id', 'character', 'character_id', 'uni_organization', 'uni_character'),
            ('battle', 'universe_id', 'universe', 'universe_id', 'uni_battle', 'uni_universe'),
            ('battle_participation', 'battle_id', 'battle', 'battle_id', 'uni_battle_participation', 'uni_battle'),
            ('battle_participation', 'character_id', 'character', 'character_id', 'uni_battle_participation', 'uni_character'),
            ('relationship', 'character1_id', 'character', 'character_id', 'uni_relationship', 'uni_character'),
            ('relationship', 'character2_id', 'character', 'character_id', 'uni_relationship', 'uni_character')):
        sql = (f'SELECT COUNT(*) AS n FROM {table_child} c WHERE c.{column} IS NOT NULL '
               f'AND NOT EXISTS (SELECT 1 FROM {table_parent} p '
               f'WHERE p.{parent_column} = c.{column})')
        try:
            orphans = db_pool.execute_query(sql, fetch='val')
            status = 'ok' if orphans == 0 else 'orphans'
        except Exception as exc:
            orphans, status = str(exc), 'error'
        checks.append({'child': table_child, 'column': column, 'parent': table_parent,
                       'orphans': orphans, 'status': status})
    views = []
    for view, label in VIEW_NAMES:
        try:
            total = db_pool.execute_query(f'SELECT COUNT(*) AS n FROM {view}', fetch='val')
            views.append({'view': view, 'label': label, 'rows': total, 'ok': True})
        except Exception as exc:
            views.append({'view': view, 'label': label, 'rows': None, 'ok': False,
                          'error': str(exc)})
    duplicates = []
    for label, sql in (
            ('alias is unique', 'SELECT COUNT(*) AS n FROM (SELECT alias FROM uni_character '
                                'GROUP BY alias HAVING COUNT(*) > 1) t'),
            ('character + power is unique', 'SELECT COUNT(*) AS n FROM (SELECT character_id, '
                                            'power_id FROM uni_character_power GROUP BY '
                                            'character_id, power_id HAVING COUNT(*) > 1) t'),
            ('battle + character is unique', 'SELECT COUNT(*) AS n FROM (SELECT battle_id, '
                                             'character_id FROM uni_battle_participation GROUP BY '
                                             'battle_id, character_id HAVING COUNT(*) > 1) t'),
            ('ordered pair + continuity is unique', 'SELECT COUNT(*) AS n FROM (SELECT '
                                                    'character1_id, character2_id, continuity '
                                                    'FROM uni_relationship GROUP BY '
                                                    'character1_id, character2_id, continuity '
                                                    'HAVING COUNT(*) > 1) t')):
        try:
            duplicates.append({'rule': label, 'violations': db_pool.execute_query(sql, fetch='val')})
        except Exception as exc:
            duplicates.append({'rule': label, 'violations': f'error: {exc}'})
    return {'checks': checks, 'views': views, 'duplicates': duplicates}


def report_text(name):
    path = artifact_path(name)
    if not path or path.suffix not in ('.md', '.sql', '.csv'):
        return None
    return path.read_text(encoding='utf-8', errors='replace')
