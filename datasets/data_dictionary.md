# Data dictionary — Marvel & DC Universe Database

Generated 2026-11-22 by `scripts/build_universe_dataset.py`. Every table is prefixed `uni_` and lives in the portal database alongside the campus schema; nothing in the campus schema is altered.

**Conventions**

- Primary keys are surrogate integers assigned in insert order.
- `universe_id` 1 = Marvel, 2 = DC.
- The empty cell in a CSV, `NULL` in SQL and a blank in the workbook all mean the same thing: not established. No cell is filled with a guess.
- Dates are ISO `YYYY-MM-DD`; years are integers.
- `original` records carry `record_origin = Original addition`.

## uni_universe

2 rows. CSV: `csv/universes.csv`. Workbook sheet: `universes`.

| Column | Type | Required | Nulls in data | Notes |
| --- | --- | --- | --- | --- |
| `universe_id` | INTEGER | no | 0 | PK —  |
| `universe_name` | VARCHAR/TEXT | yes | 0 | Display name of the publisher universe. Unique. Marvel or DC only. |
| `publisher` | VARCHAR/TEXT | yes | 0 | Publishing company that owns the characters (Marvel Comics, DC Comics). |
| `description` | VARCHAR/TEXT | yes | 0 |  |
| `continuity_type` | VARCHAR/TEXT | yes | 0 | How many continuities the universe record spans, e.g. "Comic book continuity plus film and television continuities". |

## uni_character

252 rows. CSV: `csv/characters.csv`. Workbook sheet: `characters`.

| Column | Type | Required | Nulls in data | Notes |
| --- | --- | --- | --- | --- |
| `character_id` | INTEGER | no | 0 | PK —  |
| `real_name` | VARCHAR/TEXT | no | 0 | Civilian or birth name. NULL where the character has no established name (Joker, Bane, Ra’s al Ghul, Doomsday, Lobo) — never invented. |
| `alias` | VARCHAR/TEXT | yes | 0 | Public codename. Unique, because legacy titles are disambiguated with a holder suffix ("Robin (Tim Drake)"). |
| `universe_id` | INTEGER | yes | 0 | FK —  |
| `character_type` | VARCHAR/TEXT | yes | 0 | Hero, Villain, Antihero, Supporting or Cosmic Entity. |
| `species` | VARCHAR/TEXT | yes | 0 | In-story species, e.g. Mutant, Kryptonian, Asgardian, Synthezoid. |
| `gender` | VARCHAR/TEXT | yes | 0 |  |
| `first_appearance` | VARCHAR/TEXT | no | 6 | Comic debut with issue and year. For characters created for a screen continuity, the screen debut is given and marked "screen creation". NULL where no debut is established. |
| `origin` | VARCHAR/TEXT | yes | 0 |  |
| `current_status` | VARCHAR/TEXT | yes | 0 |  |
| `alignment` | VARCHAR/TEXT | yes | 0 | Good, Evil or Neutral. Deliberately coarser than character_type: an antihero can be Neutral or Good. |
| `continuity` | VARCHAR/TEXT | yes | 0 | The specific continuity the record describes, e.g. "Marvel Comics (Earth-616)" or "DCEU (Earth-1)". Two records may share an alias across continuities only if the alias is suffixed. |
| `record_origin` | VARCHAR/TEXT | yes | 0 | Canon or Original addition. Original additions are invented for this demonstration and are labelled everywhere they appear. |

## uni_team

36 rows. CSV: `csv/teams.csv`. Workbook sheet: `teams`.

| Column | Type | Required | Nulls in data | Notes |
| --- | --- | --- | --- | --- |
| `team_id` | INTEGER | no | 0 | PK —  |
| `team_name` | VARCHAR/TEXT | yes | 0 |  |
| `universe_id` | INTEGER | yes | 0 | FK —  |
| `founding_year` | INTEGER | no | 0 | First-publication year of the team where established; in-universe year for the original additions. NULL if not established. |
| `headquarters` | VARCHAR/TEXT | no | 0 |  |
| `mission` | VARCHAR/TEXT | yes | 0 |  |
| `team_status` | VARCHAR/TEXT | yes | 0 | Active, Inactive, Dissolved or Deposed. |
| `continuity` | VARCHAR/TEXT | yes | 0 | Continuity the team belongs to; the MCU and DCEU teams are separate rows from their comic counterparts. |
| `record_origin` | VARCHAR/TEXT | no | 0 |  |

## uni_membership

208 rows. CSV: `csv/character_team_memberships.csv`. Workbook sheet: `character_team_memberships`.

| Column | Type | Required | Nulls in data | Notes |
| --- | --- | --- | --- | --- |
| `membership_id` | INTEGER | no | 0 | PK —  |
| `character_id` | INTEGER | yes | 0 | FK —  |
| `team_id` | INTEGER | yes | 0 | FK —  |
| `joining_date` | DATE | no | 0 |  |
| `departure_date` | DATE | no | 182 |  |
| `membership_status` | VARCHAR/TEXT | yes | 0 |  |
| `role` | VARCHAR/TEXT | yes | 0 |  |

## uni_power

103 rows. CSV: `csv/powers.csv`. Workbook sheet: `powers`.

| Column | Type | Required | Nulls in data | Notes |
| --- | --- | --- | --- | --- |
| `power_id` | INTEGER | no | 0 | PK —  |
| `power_name` | VARCHAR/TEXT | yes | 0 |  |
| `category` | VARCHAR/TEXT | yes | 0 | Physical, Energy, Mental, Mystical, Technological, Cosmic, Biological, Combat skill or Intellect. Combat skill and Intellect are earned training rather than powers; they are separated so a group-by on category does not put swordsmanship next to power armour. |
| `description` | VARCHAR/TEXT | yes | 0 |  |
| `power_level` | INTEGER | yes | 0 | 1-10 scale for the power itself, not for any character holding it. |

## uni_character_power

1252 rows. CSV: `csv/character_power_mapping.csv`. Workbook sheet: `character_power_mapping`.

| Column | Type | Required | Nulls in data | Notes |
| --- | --- | --- | --- | --- |
| `mapping_id` | INTEGER | no | 0 | PK —  |
| `character_id` | INTEGER | yes | 0 | FK —  |
| `power_id` | INTEGER | yes | 0 | FK —  |
| `proficiency_level` | VARCHAR/TEXT | yes | 0 |  |
| `limitations` | VARCHAR/TEXT | no | 0 |  |

## uni_content

100 rows. CSV: `csv/movies_and_series.csv`. Workbook sheet: `movies_and_series`.

| Column | Type | Required | Nulls in data | Notes |
| --- | --- | --- | --- | --- |
| `content_id` | INTEGER | no | 0 | PK —  |
| `title` | VARCHAR/TEXT | yes | 0 |  |
| `universe_id` | INTEGER | yes | 0 | FK —  |
| `release_year` | INTEGER | yes | 0 |  |
| `content_type` | VARCHAR/TEXT | yes | 0 |  |
| `director` | VARCHAR/TEXT | no | 5 |  |
| `production_studio` | VARCHAR/TEXT | yes | 0 |  |
| `duration_minutes` | INTEGER | no | 0 |  |
| `rating` | VARCHAR/TEXT | no | 0 |  |
| `synopsis` | VARCHAR/TEXT | yes | 0 |  |
| `continuity` | VARCHAR/TEXT | yes | 0 |  |

## uni_comic

141 rows. CSV: `csv/comics.csv`. Workbook sheet: `comics`.

| Column | Type | Required | Nulls in data | Notes |
| --- | --- | --- | --- | --- |
| `comic_id` | INTEGER | no | 0 | PK —  |
| `title` | VARCHAR/TEXT | yes | 0 |  |
| `universe_id` | INTEGER | yes | 0 | FK —  |
| `issue_number` | VARCHAR/TEXT | yes | 0 | Stored as text because of annuals, "1/2" issues and legacy numbering. |
| `publication_year` | INTEGER | yes | 0 |  |
| `writer` | VARCHAR/TEXT | no | 0 | Credited writer. NULL where the credit is not established here — never guessed. |
| `artist` | VARCHAR/TEXT | no | 0 | Credited penciller or artist. |
| `storyline` | VARCHAR/TEXT | no | 0 | Arc or event the issue belongs to, matching a row in uni_mission where one exists. |
| `associated_character_id` | INTEGER | no | 0 | FK — Chief character the issue is about. NULL allowed (ON DELETE SET NULL). |
| `continuity` | VARCHAR/TEXT | yes | 0 |  |

## uni_mission

60 rows. CSV: `csv/missions.csv`. Workbook sheet: `missions`.

| Column | Type | Required | Nulls in data | Notes |
| --- | --- | --- | --- | --- |
| `mission_id` | INTEGER | no | 0 | PK —  |
| `mission_name` | VARCHAR/TEXT | yes | 0 |  |
| `universe_id` | INTEGER | yes | 0 | FK —  |
| `storyline_category` | VARCHAR/TEXT | yes | 0 | Comic event, Comic arc, Film saga, Television saga or Crossover. |
| `start_year` | INTEGER | yes | 0 | First publication or release year of the storyline, not an in-universe date. |
| `end_year` | INTEGER | no | 0 | NULL for single-issue or single-film storylines. CHECK: never before start_year. |
| `description` | VARCHAR/TEXT | yes | 0 |  |
| `outcome` | VARCHAR/TEXT | yes | 0 | Short in-story result, stated as the source material states it. |
| `continuity` | VARCHAR/TEXT | yes | 0 |  |

## uni_mission_participation

264 rows. CSV: `csv/character_mission_participation.csv`. Workbook sheet: `character_mission_participation`.

| Column | Type | Required | Nulls in data | Notes |
| --- | --- | --- | --- | --- |
| `participation_id` | INTEGER | no | 0 | PK —  |
| `character_id` | INTEGER | yes | 0 | FK —  |
| `mission_id` | INTEGER | yes | 0 | FK —  |
| `role` | VARCHAR/TEXT | yes | 0 |  |
| `outcome` | VARCHAR/TEXT | yes | 0 |  |
| `survival_status` | VARCHAR/TEXT | yes | 0 |  |

## uni_organization

51 rows. CSV: `csv/organizations.csv`. Workbook sheet: `organizations`.

| Column | Type | Required | Nulls in data | Notes |
| --- | --- | --- | --- | --- |
| `organization_id` | INTEGER | no | 0 | PK —  |
| `organization_name` | VARCHAR/TEXT | yes | 0 |  |
| `universe_id` | INTEGER | yes | 0 | FK —  |
| `organization_type` | VARCHAR/TEXT | yes | 0 | Nation state, intelligence agency, conglomerate, cult, corps, relief corps and so on. |
| `headquarters` | VARCHAR/TEXT | no | 0 |  |
| `leader_character_id` | INTEGER | no | 0 | FK — Current or most recent leader. FK with ON DELETE SET NULL. |
| `objectives` | VARCHAR/TEXT | yes | 0 |  |
| `continuity` | VARCHAR/TEXT | yes | 0 |  |
| `record_origin` | VARCHAR/TEXT | no | 0 |  |

## uni_battle

80 rows. CSV: `csv/battles.csv`. Workbook sheet: `battles`.

| Column | Type | Required | Nulls in data | Notes |
| --- | --- | --- | --- | --- |
| `battle_id` | INTEGER | no | 0 | PK —  |
| `battle_name` | VARCHAR/TEXT | yes | 0 |  |
| `universe_id` | INTEGER | yes | 0 | FK —  |
| `location` | VARCHAR/TEXT | yes | 0 |  |
| `year` | INTEGER | yes | 0 | In-universe or story year of the battle, which for a film is the year the film is set. |
| `description` | VARCHAR/TEXT | yes | 0 |  |
| `winner` | VARCHAR/TEXT | yes | 0 | Short description of the winning side, including "Draw" where the story ends without one. |
| `casualties` | INTEGER | no | 0 | FICTIONAL figure for this battle only. NULL where the story gives no number. These are numbers from fiction, not estimates of anything real. |
| `continuity` | VARCHAR/TEXT | yes | 0 |  |

## uni_battle_participation

417 rows. CSV: `csv/battle_participation.csv`. Workbook sheet: `battle_participation`.

| Column | Type | Required | Nulls in data | Notes |
| --- | --- | --- | --- | --- |
| `participation_id` | INTEGER | no | 0 | PK —  |
| `battle_id` | INTEGER | yes | 0 | FK —  |
| `character_id` | INTEGER | yes | 0 | FK —  |
| `side` | VARCHAR/TEXT | yes | 0 | Named side in the battle, e.g. "Avengers and allies". |
| `battle_result` | VARCHAR/TEXT | yes | 0 | Victorious, Defeated or Stalemate, from that character perspective. |
| `status` | VARCHAR/TEXT | yes | 0 | Survived, Killed, Presumed dead or Unknown after the battle. |

## uni_relationship

188 rows. CSV: `csv/character_relationships.csv`. Workbook sheet: `character_relationships`.

| Column | Type | Required | Nulls in data | Notes |
| --- | --- | --- | --- | --- |
| `relationship_id` | INTEGER | no | 0 | PK —  |
| `character1_id` | INTEGER | yes | 0 | FK —  |
| `character2_id` | INTEGER | yes | 0 | FK —  |
| `relationship_type` | VARCHAR/TEXT | yes | 0 |  |
| `description` | VARCHAR/TEXT | yes | 0 |  |
| `continuity` | VARCHAR/TEXT | yes | 0 |  |

## Views

| View | Purpose |
| --- | --- |
| `v_uni_character_profile` | Character card with team count, power count and best power level. |
| `v_uni_universe_summary` | Marvel vs DC head-counts across all seven child tables. |
| `v_uni_team_roster` | One row per membership with the team, the character and the role. |
| `v_uni_power_distribution` | Holders, heroes and villains per power. |
| `v_uni_battle_summary` | Combatants and losses per battle. |
| `v_uni_relationship_network` | Ordered pairs with both aliases and the continuity. |
| `v_uni_screen_catalogue` | Films and series with universe, year and credits. |

## Referential rules

| Child | Column | Parent | Nullable |
| --- | --- | --- | --- |
| `characters` | `universe_id` | `universes` | no |
| `teams` | `universe_id` | `universes` | no |
| `character_team_memberships` | `character_id` | `characters` | no |
| `character_team_memberships` | `team_id` | `teams` | no |
| `character_power_mapping` | `character_id` | `characters` | no |
| `character_power_mapping` | `power_id` | `powers` | no |
| `movies_and_series` | `universe_id` | `universes` | no |
| `comics` | `universe_id` | `universes` | no |
| `comics` | `associated_character_id` | `characters` | no |
| `missions` | `universe_id` | `universes` | no |
| `character_mission_participation` | `character_id` | `characters` | no |
| `character_mission_participation` | `mission_id` | `missions` | no |
| `organizations` | `universe_id` | `universes` | no |
| `organizations` | `leader_character_id` | `characters` | no |
| `battles` | `universe_id` | `universes` | no |
| `battle_participation` | `battle_id` | `battles` | no |
| `battle_participation` | `character_id` | `characters` | no |
| `character_relationships` | `character1_id` | `characters` | no |
| `character_relationships` | `character2_id` | `characters` | no |
