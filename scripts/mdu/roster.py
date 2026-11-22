"""Battle participation for the Marvel & DC Universe Database.

The participation table is derived rather than hand-typed, so that 80 battles with 320
rows stay internally consistent: the rosters live in `battle_rosters.py`, one list per
side, and this module only does the bookkeeping.

Rules
-----
1. A battle's roster must come from its own continuity. A key that is unknown, or that
   belongs to a different continuity or the other publisher, raises instead of being
   substituted: a wrong body in a battle is worse than a build failure.
2. The side column carries the in-world side name for that battle (for example
   "Avengers and allies" / "Thanos forces"), so a group-by on `side` groups a coalition
   rather than a coin-flip.
3. Result is derived, not invented: the heroes' side wins unless the battle is listed in
   `VILLAIN_WINS`, and a battle whose recorded winner starts with "Draw" or is recorded
   as having no victor gives every participant `Stalemate`.
4. `status` is Survived unless the character is listed in `CASUALTIES` for that battle.
   Casualties are only recorded where the story actually kills or removes someone.
"""

from .battle_rosters import ALL_ROSTERS

# Battle keys whose recorded winner is the villain side.
VILLAIN_WINS = {
    'battle_titan', 'battle_knowhere', 'battle_vormir', 'battle_gotham_knightfall',
    'battle_judas_contract', 'battle_genosha', 'battle_bane_occupation',
    'battle_gotham_bane', 'battle_thanagar', 'battle_mars', 'battle_darkseid_war_final',
    'battle_woodward_gala', 'battle_earth_838', 'battle_babel',
}

# Battle keys where the recorded outcome is a draw, a stalemate or no victor.
STALEMATES = {
    'battle_berlin_airport', 'battle_metropolis_doomsday_comics', 'battle_flashpoint_war',
    'battle_kingdom_come', 'battle_smallville_meteor', 'battle_mount_wundagore',
}

# battle key -> {character key: status}. Anything not listed is Survived.
CASUALTIES = {
    'battle_new_york': {'phil_coulson': 'Killed'},
    'battle_wakanda': {'mcu_corvus_glaive': 'Killed', 'mcu_proxima_midnight': 'Killed',
                       'mcu_cull_obsidian': 'Killed'},
    'battle_titan': {'mcu_ebony_maw': 'Killed'},
    'battle_endgame': {'mcu_iron_man': 'Killed', 'mcu_black_widow': 'Killed',
                       'mcu_thanos': 'Killed'},
    'battle_sokovia': {'mcu_ultron': 'Killed'},
    'battle_asgard_surtur': {'mcu_hela': 'Killed', 'mcu_loki': 'Presumed dead'},
    'battle_vormir': {'mcu_gamora': 'Killed', 'mcu_black_widow': 'Killed'},
    'battle_tva_finale': {'mcu_he_who_remains': 'Killed'},
    'battle_knowhere': {'mcu_gamora': 'Killed'},
    'battle_multiverse_incursion': {'mcu_scarlet_witch': 'Presumed dead'},
    'battle_mount_wundagore': {'mcu_wanda_title': 'Presumed dead'},
    'battle_metropolis': {'dceu_zod': 'Killed'},
    'battle_doomsday': {'dceu_superman': 'Killed', 'dceu_zod': 'Killed'},
    'battle_steppenwolf': {'dceu_steppenwolf': 'Killed'},
    'battle_liberty_island_2': {'dceu_steppenwolf': 'Killed'},
    'battle_metropolis_doomsday_comics': {'superman': 'Killed', 'doomsday': 'Killed'},
    'battle_dark_phoenix_moon': {'jean_grey': 'Killed'},
    'battle_crisis_anti_monitor': {'flash': 'Killed', 'supergirl': 'Killed'},
    'battle_flashpoint_war': {'reverse_flash': 'Killed', 'aquaman': 'Killed',
                              'wonder_woman': 'Killed'},
    'battle_siege_asgard': {'bullseye': 'Killed'},
    'battle_blackest_night_final': {'solomon_grundy': 'Killed'},
    'battle_judas_contract': {'terra_616': 'Killed'},
    'battle_hel': {'mcu_loki': 'Killed'},
    'battle_genosha': {},
    'battle_smallville_meteor': {},
}

# Side labels per continuity, as (hero side, villain side).
SIDE_LABELS = {
    'Marvel Cinematic Universe (Earth-199999)': ('Avengers and allies', 'Thanos forces'),
    'DCEU (Earth-1)': ('Justice League and allies', 'Apokolips and allies'),
    'Marvel Comics (Earth-616)': ('Earth-616 heroes', 'Earth-616 villains'),
    'DC Comics (New Earth/Prime Earth)': ('New Earth heroes', 'New Earth villains'),
    'DC Comics (Arrowverse)': ('Team Arrow and allies', 'League of Assassins'),
    'DC Comics (Dark Knight Trilogy)': ('Batman and the GCPD', "Bane's militia"),
    'DC Comics (Titans Series)': ('Titans', 'Deathstroke'),
    'DC Comics (Smallville continuity)': ('Smallville defenders', 'No opposing side'),
    'Marvel Comics (X-Men Film Series)': ('X-Men', 'Brotherhood of Mutants'),
}
DEFAULT_SIDES = ('Defending force', 'Attacking force')


# Continuities with no character rows of their own. A battle in one of these casts the
# same names in their comic-book record; see the note in `battle_rosters.py`.
FILM_STANDIN_CONTINUITIES = {
    'DC Comics (Dark Knight Trilogy)': 'DC Comics (New Earth/Prime Earth)',
    'DC Comics (Titans Series)': 'Marvel Comics (Earth-616)',  # placeholder, see below
    'Marvel Comics (X-Men Film Series)': 'Marvel Comics (Earth-616)',
}
FILM_STANDIN_CONTINUITIES['DC Comics (Titans Series)'] = 'DC Comics (New Earth/Prime Earth)'

# battle key -> the continuity the cast physically comes from, when it differs.
STANDBY = {
    'battle_gotham_bane': 'DC Comics (New Earth/Prime Earth)',
    'battle_gotham_ferry': 'DC Comics (New Earth/Prime Earth)',
    'battle_gotham_warehouse': 'DC Comics (New Earth/Prime Earth)',
    'battle_titans_tower_dceu': 'DC Comics (New Earth/Prime Earth)',
    'battle_statue_liberty': 'Marvel Comics (Earth-616)',
    'battle_alkali_lake': 'Marvel Comics (Earth-616)',
    'battle_stryker_base': 'Marvel Comics (Earth-616)',
}


def _validate(battle_key, continuity, universe, roster, by_key):
    """Every roster key must exist, belong to the allowed continuity and the same publisher."""
    allowed = STANDBY.get(battle_key, continuity)
    for group in ('heroes', 'villains'):
        for key in roster.get(group, []):
            character = by_key.get(key)
            if character is None:
                raise KeyError(f'{battle_key}: no such character key {key!r}')
            if character['continuity'] != allowed:
                raise ValueError(
                    f'{battle_key}: {key!r} is in {character["continuity"]!r}, '
                    f'not the allowed continuity {allowed!r}')
            if character['universe'] != universe:
                raise ValueError(f'{battle_key}: {key!r} is in the other publisher')


def build_battle_participation(battles, characters):
    """Return a list of dicts: battle key, character key, side, result, status."""
    by_key = {c['key']: c for c in characters}
    rows = []
    for battle in battles:
        key, name, universe, location, year, description, winner, casualties, continuity = battle
        roster = ALL_ROSTERS.get(key)
        if roster is None:
            raise KeyError(f'{key}: no curated roster in mdu/battle_rosters.py')
        _validate(key, continuity, universe, roster, by_key)

        hero_side, villain_side = SIDE_LABELS.get(continuity, DEFAULT_SIDES)
        stalemate = key in STALEMATES or winner.lower().startswith('no victor')
        villain_won = key in VILLAIN_WINS

        for group, side in (('heroes', hero_side), ('villains', villain_side)):
            for character_key in roster.get(group, []):
                if stalemate:
                    result = 'Stalemate'
                elif villain_won:
                    result = 'Defeated' if group == 'heroes' else 'Victorious'
                else:
                    result = 'Victorious' if group == 'heroes' else 'Defeated'
                status = CASUALTIES.get(key, {}).get(character_key, 'Survived')
                rows.append({'battle': key, 'character': character_key, 'side': side,
                             'result': result, 'status': status,
                             'universe': universe, 'continuity': continuity})
    return rows
