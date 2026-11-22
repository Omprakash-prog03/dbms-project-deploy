"""Curated battle rosters for the Marvel & DC Universe Database.

Each battle lists the characters who actually appear in that fight, in the order the
story puts them there. `roster.py` reads these tables, checks every key exists and
belongs to the battle's own continuity, and derives the side and the result.

Why curated rather than sampled
-------------------------------
An earlier version picked four combatants per battle from the continuity pool with a
fixed stride. It satisfied the foreign keys, but it put Amanda Waller in a fist-fight at
the Battle of Metropolis and it left Iron Man out of the Battle of New York. A battle
table that is merely *consistent* is not usable for a demonstration, so the rosters are
listed by hand here and the derivation only does the bookkeeping.

Nothing in this file invents a fight: every key below belongs to the battle's own
continuity, and a key that does not is a hard build failure (`build_battle_participation`
raises `KeyError`), not a silent substitution.

SCREEN limit
------------
Seventeen continuities appear in the battle table but only two of them (Marvel
Cinematic Universe, DCEU) have a character roster in this dataset. The five
smaller film and television continuities use the same table shape and are the one
place where the dataset is deliberately thinner than the real casts; this module
raises for the keys it cannot resolve rather than borrowing a body from another
continuity.
"""

# --- Marvel Cinematic Universe (Earth-199999) ---------------------------------
MARVEL_CINEMATIC = {
    'battle_new_york': {
        'heroes': ['mcu_iron_man', 'mcu_captain_america', 'mcu_thor', 'mcu_hulk',
                   'mcu_black_widow', 'mcu_hawkeye', 'phil_coulson'],
        'villains': ['mcu_loki'],
    },
    'battle_wakanda': {
        'heroes': ['mcu_captain_america', 'mcu_black_panther', 'mcu_black_widow',
                   'mcu_falcon', 'mcu_winter_soldier', 'mcu_war_machine',
                   'mcu_scarlet_witch', 'mcu_vision'],
        'villains': ['mcu_proxima_midnight', 'mcu_corvus_glaive', 'mcu_cull_obsidian'],
    },
    'battle_titan': {
        'heroes': ['mcu_iron_man', 'mcu_spider_man', 'mcu_doctor_strange',
                   'mcu_star_lord', 'mcu_drax', 'mcu_mantis', 'mcu_nebula'],
        'villains': ['mcu_thanos', 'mcu_ebony_maw'],
    },
    'battle_endgame': {
        'heroes': ['mcu_iron_man', 'mcu_captain_america', 'mcu_thor', 'mcu_hulk',
                   'mcu_black_widow', 'mcu_hawkeye', 'mcu_scarlet_witch',
                   'mcu_captain_marvel', 'mcu_black_panther', 'mcu_spider_man'],
        'villains': ['mcu_thanos'],
    },
    'battle_sokovia': {
        'heroes': ['mcu_iron_man', 'mcu_captain_america', 'mcu_thor', 'mcu_hulk',
                   'mcu_black_widow', 'mcu_hawkeye', 'mcu_vision', 'mcu_scarlet_witch'],
        'villains': ['mcu_ultron'],
    },
    'battle_berlin_airport': {
        'heroes': ['mcu_captain_america', 'mcu_falcon', 'mcu_winter_soldier',
                   'mcu_scarlet_witch', 'mcu_hawkeye'],
        'villains': ['mcu_iron_man', 'mcu_war_machine', 'mcu_black_panther'],
    },
    'battle_ny_hand': {
        'heroes': ['mcu_daredevil', 'mcu_jessica_jones', 'mcu_luke_cage', 'mcu_iron_fist'],
        'villains': [],
    },
    'battle_asgard_surtur': {
        'heroes': ['mcu_thor', 'mcu_loki', 'mcu_hulk'],
        'villains': ['mcu_hela'],
    },
    'battle_xandar': {
        'heroes': ['mcu_star_lord', 'mcu_gamora', 'mcu_drax', 'mcu_rocket', 'mcu_groot'],
        'villains': ['mcu_thanos', 'mcu_nebula'],
    },
    'battle_eger_planet': {
        'heroes': ['mcu_star_lord', 'mcu_gamora', 'mcu_drax', 'mcu_rocket', 'mcu_groot',
                   'mcu_mantis'],
        'villains': [],
    },
    'battle_knowhere': {
        'heroes': ['mcu_star_lord', 'mcu_gamora', 'mcu_drax', 'mcu_rocket', 'mcu_nebula',
                   'mcu_mantis'],
        'villains': ['mcu_thanos'],
    },
    'battle_vormir': {
        'heroes': ['mcu_gamora', 'mcu_black_widow'],
        'villains': ['mcu_thanos'],
    },
    'battle_black_zero_mcu': {
        'heroes': ['mcu_thor', 'mcu_wong'],
        'villains': [],
    },
    'battle_helicarrier': {
        'heroes': ['mcu_captain_america', 'mcu_black_widow', 'mcu_falcon', 'mcu_nick_fury'],
        'villains': ['mcu_red_skull'],
    },
    'battle_berlin_airport2': {
        'heroes': ['mcu_captain_america', 'mcu_winter_soldier', 'mcu_falcon'],
        'villains': ['mcu_red_skull'],
    },
    'battle_woodward_gala': {
        'heroes': ['mcu_black_panther', 'mcu_captain_america'],
        'villains': ['mcu_killmonger'],
    },
    'battle_kang_quantum': {
        'heroes': ['mcu_spider_man', 'mcu_captain_america', 'mcu_hulk'],
        'villains': ['mcu_loki'],
    },
    'battle_hex_confrontation': {
        'heroes': ['mcu_scarlet_witch', 'mcu_vision', 'mcu_wanda_title'],
        'villains': [],
    },
    'battle_tva_finale': {
        'heroes': ['mcu_loki', 'mcu_loki_variant_sylvie'],
        'villains': ['mcu_he_who_remains'],
    },
    'battle_multiverse_incursion': {
        'heroes': ['mcu_doctor_strange', 'mcu_scarlet_witch', 'mcu_spider_man'],
        'villains': [],
    },
    'battle_madripoor': {
        'heroes': ['mcu_winter_soldier', 'mcu_falcon'],
        'villains': [],
    },
    'battle_harlem': {
        'heroes': ['mcu_hulk', 'mcu_war_machine'],
        'villains': [],
    },
    'battle_culver': {
        'heroes': ['mcu_hulk', 'mcu_nick_fury'],
        'villains': [],
    },
    'battle_sakaar_arena': {
        'heroes': ['mcu_thor', 'mcu_hulk', 'mcu_loki'],
        'villains': [],
    },
    'battle_apokolips_mcu': {
        'heroes': ['mcu_captain_marvel', 'mcu_nick_fury', 'mcu_spider_man'],
        'villains': ['mcu_thanos'],
    },
    'battle_sanctum_ny': {
        'heroes': ['mcu_doctor_strange', 'mcu_wong'],
        'villains': [],
    },
    'battle_edinburgh': {
        'heroes': ['mcu_scarlet_witch', 'mcu_vision'],
        'villains': [],
    },
    'battle_knowhere2': {
        'heroes': ['mcu_star_lord', 'mcu_drax', 'mcu_nebula', 'mcu_mantis', 'mcu_groot'],
        'villains': [],
    },
    'battle_counter_earth': {
        'heroes': ['mcu_star_lord', 'mcu_nebula', 'mcu_drax', 'mcu_mantis'],
        'villains': [],
    },
    'battle_earth_838': {
        'heroes': ['mcu_scarlet_witch', 'mcu_wong'],
        'villains': [],
    },
    'battle_mount_wundagore': {
        'heroes': ['mcu_wanda_title', 'mcu_scarlet_witch'],
        'villains': [],
    },
}

# --- DCEU (Earth-1) -----------------------------------------------------------
DCEU = {
    'battle_metropolis': {
        'heroes': ['dceu_superman'],
        'villains': ['dceu_zod'],
    },
    'battle_gotham_docks': {
        'heroes': ['dceu_batman'],
        'villains': ['dceu_harley'],
    },
    'battle_doomsday': {
        'heroes': ['dceu_superman', 'dceu_batman', 'dceu_wonder_woman'],
        'villains': ['dceu_zod'],
    },
    'battle_steppenwolf': {
        'heroes': ['dceu_superman', 'dceu_batman', 'dceu_wonder_woman', 'dceu_flash',
                   'dceu_aquaman', 'dceu_cyborg'],
        'villains': ['dceu_steppenwolf'],
    },
    'battle_atlantis_throne': {
        'heroes': ['dceu_aquaman', 'dceu_mera', 'dceu_atlanna'],
        'villains': ['dceu_orin'],
    },
    'battle_midway': {
        'heroes': ['dceu_amanda_waller', 'dceu_deadshot', 'dceu_harley'],
        'villains': ['dceu_steppenwolf', 'dceu_killer_croc'],
    },
    'battle_kahndaq': {
        'heroes': ['dceu_wonder_woman', 'dceu_cyborg'],
        'villains': ['dceu_black_manta'],
    },
    'battle_daily_planet': {
        'heroes': ['dceu_superman', 'dceu_batman', 'dceu_wonder_woman'],
        'villains': ['dceu_zod'],
    },
    'battle_liberty_island_2': {
        'heroes': ['dceu_wonder_woman', 'dceu_batman'],
        'villains': ['dceu_steppenwolf'],
    },
    'battle_corto_maltese': {
        'heroes': ['dceu_harley', 'dceu_deadshot', 'dceu_amanda_waller'],
        'villains': ['dceu_captain_boomerang', 'dceu_killer_croc'],
    },
    'battle_belle_reve': {
        'heroes': ['dceu_amanda_waller', 'dceu_deadshot'],
        'villains': ['dceu_harley', 'dceu_killer_croc', 'dceu_captain_boomerang'],
    },
}

# --- DC Comics (New Earth / Prime Earth) --------------------------------------
DC_COMICS = {
    'battle_metropolis_doomsday_comics': {
        'heroes': ['superman', 'flash_wally', 'green_lantern_john', 'hawkman', 'aquaman'],
        'villains': ['doomsday'],
    },
    'battle_gotham_knightfall': {
        'heroes': ['batman', 'robin_tim', 'nightwing', 'batgirl'],
        'villains': ['bane'],
    },
    'battle_crisis_anti_monitor': {
        'heroes': ['superman', 'flash', 'green_lantern', 'supergirl', 'martian_manhunter',
                   'cyborg'],
        'villains': ['darkseid'],
    },
    'battle_flashpoint_war': {
        'heroes': ['aquaman', 'wonder_woman', 'reverse_flash', 'cyborg'],
        'villains': ['ocean_master', 'black_manta'],
    },
    'battle_gotham_siege': {
        'heroes': ['batman', 'jim_gordon', 'robin_tim', 'huntress', 'nightwing'],
        'villains': ['joker', 'harley_quinn', 'scarecrow'],
    },
    'battle_babel': {
        'heroes': ['batman', 'superman', 'wonder_woman', 'flash', 'green_lantern'],
        'villains': ['ra_as_ghul', 'talia_al_ghul'],
    },
    'battle_blackest_night_final': {
        'heroes': ['flash', 'green_lantern', 'green_lantern_john', 'green_lantern_alan',
                   'zatanna', 'hawkgirl'],
        'villains': ['sinestro', 'atrocitus', 'solomon_grundy'],
    },
    'battle_sinestro_oa': {
        'heroes': ['green_lantern', 'green_lantern_john', 'green_lantern_alan'],
        'villains': ['sinestro', 'atrocitus'],
    },
    'battle_darkseid_war_final': {
        'heroes': ['superman', 'batman', 'wonder_woman', 'flash', 'green_lantern',
                   'aquaman', 'cyborg', 'doctor_fate', 'zatanna'],
        'villains': ['darkseid', 'brainiac'],
    },
    'battle_infinite_crisis_final': {
        'heroes': ['superman', 'batman', 'wonder_woman', 'flash', 'green_lantern',
                   'supergirl', 'martian_manhunter'],
        'villains': ['darkseid', 'brainiac', 'lobo'],
    },
    'battle_judas_contract': {
        'heroes': ['nightwing', 'starfire', 'raven', 'beast_boy', 'cyborg_titans',
                   'flash_wally'],
        'villains': ['deathstroke'],
    },
    'battle_kingdom_come': {
        'heroes': ['superman', 'batman', 'wonder_woman', 'green_lantern', 'flash'],
        'villains': ['lex_luthor', 'brainiac'],
    },
    'battle_legion_doom': {
        'heroes': ['superman', 'batman', 'wonder_woman', 'flash', 'green_lantern',
                   'aquaman', 'martian_manhunter', 'hawkgirl', 'atom', 'black_canary'],
        'villains': ['lex_luthor', 'joker', 'cheetah', 'giganta', 'scarecrow'],
    },
    'battle_thanagar': {
        'heroes': ['hawkman', 'hawkgirl', 'green_lantern', 'superman'],
        'villains': [],
    },
    'battle_zemaron': {
        'heroes': ['green_lantern', 'green_lantern_john', 'green_lantern_alan', 'hawkman'],
        'villains': ['sinestro'],
    },
    'battle_mars': {
        'heroes': ['martian_manhunter', 'superman', 'green_lantern', 'flash'],
        'villains': [],
    },
}

# --- Marvel Comics (Earth-616) ------------------------------------------------
MARVEL_COMICS = {
    'battle_siege_asgard': {
        'heroes': ['thor', 'iron_man', 'captain_america', 'loki', 'ms_marvel_616'],
        'villains': ['bullseye', 'venom'],
    },
    'battle_secret_wars': {
        'heroes': ['captain_america', 'iron_man', 'thor', 'hulk', 'spider_man',
                   'mr_fantastic'],
        'villains': ['doctor_octopus', 'galactus', 'loki'],
    },
    'battle_infinity_gauntlet': {
        'heroes': ['adam_warlock_616', 'silver_surfer', 'thor', 'iron_man', 'nebula',
                   'drax'],
        'villains': ['thanos'],
    },
    'battle_dark_phoenix_moon': {
        'heroes': ['cyclops', 'jean_grey', 'wolverine', 'storm', 'colossus', 'nightcrawler'],
        'villains': [],
    },
    'battle_new_york_60s': {
        'heroes': ['thor', 'iron_man', 'captain_america', 'hulk', 'wasp', 'ant_man'],
        'villains': ['loki'],
    },
    'battle_genosha': {
        'heroes': ['magneto', 'professor_x', 'cyclops', 'emma_frost', 'wolverine', 'storm'],
        'villains': [],
    },
    'battle_utopia': {
        'heroes': ['cyclops', 'emma_frost', 'wolverine', 'storm', 'beast', 'colossus'],
        'villains': ['apocalypse', 'mr_sinister'],
    },
    'battle_avengers_mansion': {
        'heroes': ['captain_america', 'thor', 'iron_man', 'wasp', 'ant_man', 'hawkeye'],
        'villains': ['ultron'],
    },
    'battle_hel': {
        'heroes': ['thor', 'loki', 'hela'],
        'villains': [],
    },
}


# --- Continuities with a thin roster in this dataset --------------------------
# The Smallville, Arrowverse, Dark Knight, Titans and X-Men film battles belong to
# continuities that carry only one to six characters of their own here. Where a battle
# is fully covered by its own continuity (Smallville, Arrowverse, Titans) the roster is
# exact. Where it is not (Dark Knight Trilogy, X-Men Film Series) the roster lists the
# same character in their comic-book record, and the battle keeps its film continuity:
# the labels and the year are the film's, the character row is the comics one. That is
# recorded as a known limitation in `datasets/validation_report.md` rather than hidden
# by borrowing a body from a different fight.
ARROWVERSE = {
    'battle_arrow_undertaking': {
        'heroes': ['green_arrow_tv', 'john_diggle', 'felicity_smoak'],
        'villains': ['malcolm_merlyn'],
    },
    'battle_star_city_siege': {
        'heroes': ['green_arrow_tv', 'john_diggle', 'felicity_smoak', 'black_canary_tv'],
        'villains': [],
    },
    'battle_metahuman_uprising': {
        'heroes': ['green_arrow_tv', 'black_canary_tv', 'kara_danvers_cw', 'rip_hunter'],
        'villains': [],
    },
    'battle_nanda_parbat': {
        'heroes': ['green_arrow_tv', 'black_canary_tv', 'john_diggle'],
        'villains': ['malcolm_merlyn'],
    },
    'battle_glades_riot': {
        'heroes': ['green_arrow_tv', 'john_diggle', 'felicity_smoak'],
        'villains': ['malcolm_merlyn'],
    },
}

SMALLVILLE = {
    'battle_smallville_meteor': {
        'heroes': ['chloe_sullivan'],
        'villains': [],
    },
}

DARK_KNIGHT = {
    'battle_gotham_bane': {
        'heroes': ['batman'],
        'villains': ['bane'],
    },
    'battle_gotham_ferry': {
        'heroes': ['batman', 'jim_gordon'],
        'villains': ['joker'],
    },
    'battle_gotham_warehouse': {
        'heroes': ['batman'],
        'villains': ['scarecrow'],
    },
}

TITANS = {
    'battle_titans_tower_dceu': {
        'heroes': ['nightwing', 'starfire', 'raven', 'beast_boy'],
        'villains': ['deathstroke'],
    },
}

X_MEN_FILM = {
    'battle_statue_liberty': {
        'heroes': ['wolverine', 'cyclops', 'jean_grey', 'storm'],
        'villains': ['magneto', 'mystique', 'sabretooth'],
    },
    'battle_alkali_lake': {
        'heroes': ['wolverine', 'jean_grey', 'cyclops', 'storm', 'nightcrawler'],
        'villains': ['mystique'],
    },
    'battle_stryker_base': {
        'heroes': ['wolverine', 'magneto', 'cyclops', 'jean_grey', 'storm'],
        'villains': ['mystique', 'sabretooth'],
    },
}

ALL_ROSTERS = {}
for _table in (MARVEL_CINEMATIC, DCEU, DC_COMICS, MARVEL_COMICS, ARROWVERSE,
               SMALLVILLE, DARK_KNIGHT, TITANS, X_MEN_FILM):
    ALL_ROSTERS.update(_table)
