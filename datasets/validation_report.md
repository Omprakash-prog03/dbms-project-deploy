# Validation report — Marvel & DC Universe Database

Generated 2026-11-22. Checks run in-process against the assembled dataset before any row was written to the database, and again after loading (see `insertion_log.md`).

**3,154 rows across 14 entities.**

## Row counts

| Entity | Table | Rows |
| --- | --- | ---: |
| universes | `universes` | 2 |
| characters | `characters` | 252 |
| teams | `teams` | 36 |
| memberships | `character_team_memberships` | 208 |
| powers | `powers` | 103 |
| character_powers | `character_power_mapping` | 1,252 |
| contents | `movies_and_series` | 100 |
| comics | `comics` | 141 |
| missions | `missions` | 60 |
| mission_participation | `character_mission_participation` | 264 |
| organizations | `organizations` | 51 |
| battles | `battles` | 80 |
| battle_participation | `battle_participation` | 417 |
| relationships | `character_relationships` | 188 |

## Primary keys

| Table | Key column | Rows | Distinct | Duplicates | Missing |
| --- | --- | ---: | ---: | --- | --- |
| `character_team_memberships` | `membership_id` | 208 | 208 | none | none |
| `character_power_mapping` | `mapping_id` | 1,252 | 1,252 | none | none |
| `movies_and_series` | `content_id` | 100 | 100 | none | none |
| `comics` | `comic_id` | 141 | 141 | none | none |
| `character_mission_participation` | `participation_id` | 264 | 264 | none | none |
| `organizations` | `organization_id` | 51 | 51 | none | none |
| `battle_participation` | `participation_id` | 417 | 417 | none | none |
| `character_relationships` | `relationship_id` | 188 | 188 | none | none |

## Foreign keys

19 relationships checked, **0 orphan rows**.

| Child | Column | Parent | Checked | Orphans | Null (allowed) |
| --- | --- | --- | ---: | ---: | ---: |
| `characters` | `universe_id` | `universes` | 252 | 0 | 0 |
| `teams` | `universe_id` | `universes` | 36 | 0 | 0 |
| `character_team_memberships` | `character_id` | `characters` | 208 | 0 | 0 |
| `character_team_memberships` | `team_id` | `teams` | 208 | 0 | 0 |
| `character_power_mapping` | `character_id` | `characters` | 1,252 | 0 | 0 |
| `character_power_mapping` | `power_id` | `powers` | 1,252 | 0 | 0 |
| `movies_and_series` | `universe_id` | `universes` | 100 | 0 | 0 |
| `comics` | `universe_id` | `universes` | 141 | 0 | 0 |
| `comics` | `associated_character_id` | `characters` | 141 | 0 | 0 |
| `missions` | `universe_id` | `universes` | 60 | 0 | 0 |
| `character_mission_participation` | `character_id` | `characters` | 264 | 0 | 0 |
| `character_mission_participation` | `mission_id` | `missions` | 264 | 0 | 0 |
| `organizations` | `universe_id` | `universes` | 51 | 0 | 0 |
| `organizations` | `leader_character_id` | `characters` | 51 | 0 | 0 |
| `battles` | `universe_id` | `universes` | 80 | 0 | 0 |
| `battle_participation` | `battle_id` | `battles` | 417 | 0 | 0 |
| `battle_participation` | `character_id` | `characters` | 417 | 0 | 0 |
| `character_relationships` | `character1_id` | `characters` | 188 | 0 | 0 |
| `character_relationships` | `character2_id` | `characters` | 188 | 0 | 0 |

## Duplicate detection

11 uniqueness rules checked, **0 violations**.

| Entity | Rule | Violations |
| --- | --- | ---: |
| `characters` | alias is unique | 0 |
| `characters` | no real name invented where none exists | 0 |
| `character_team_memberships` | character + team + joining date is unique | 0 |
| `character_power_mapping` | character + power is unique | 0 |
| `character_mission_participation` | character + mission is unique | 0 |
| `battle_participation` | battle + character is unique | 0 |
| `character_relationships` | ordered pair + continuity is unique | 0 |
| `movies_and_series` | title + release year + content type is unique | 0 |
| `comics` | title + issue + year is unique | 0 |
| `organizations` | universe + name is unique | 0 |
| `battles` | universe + name is unique | 0 |

## Missing values

Required columns are all populated: **True**. The optional rows below are NULL by design, not by omission.

| Table | Column | Rule | Rows | Blank | OK |
| --- | --- | --- | ---: | ---: | --- |
| `universes` | `universe_name` | required | 2 | 0 | yes |
| `universes` | `publisher` | required | 2 | 0 | yes |
| `universes` | `description` | required | 2 | 0 | yes |
| `universes` | `continuity_type` | required | 2 | 0 | yes |
| `characters` | `alias` | required | 252 | 0 | yes |
| `characters` | `universe_id` | required | 252 | 0 | yes |
| `characters` | `character_type` | required | 252 | 0 | yes |
| `characters` | `species` | required | 252 | 0 | yes |
| `characters` | `gender` | required | 252 | 0 | yes |
| `characters` | `origin` | required | 252 | 0 | yes |
| `characters` | `current_status` | required | 252 | 0 | yes |
| `characters` | `alignment` | required | 252 | 0 | yes |
| `characters` | `continuity` | required | 252 | 0 | yes |
| `characters` | `record_origin` | required | 252 | 0 | yes |
| `teams` | `team_name` | required | 36 | 0 | yes |
| `teams` | `universe_id` | required | 36 | 0 | yes |
| `teams` | `mission` | required | 36 | 0 | yes |
| `teams` | `team_status` | required | 36 | 0 | yes |
| `teams` | `continuity` | required | 36 | 0 | yes |
| `character_team_memberships` | `character_id` | required | 208 | 0 | yes |
| `character_team_memberships` | `team_id` | required | 208 | 0 | yes |
| `character_team_memberships` | `membership_status` | required | 208 | 0 | yes |
| `character_team_memberships` | `role` | required | 208 | 0 | yes |
| `powers` | `power_name` | required | 103 | 0 | yes |
| `powers` | `category` | required | 103 | 0 | yes |
| `powers` | `description` | required | 103 | 0 | yes |
| `powers` | `power_level` | required | 103 | 0 | yes |
| `character_power_mapping` | `character_id` | required | 1,252 | 0 | yes |
| `character_power_mapping` | `power_id` | required | 1,252 | 0 | yes |
| `character_power_mapping` | `proficiency_level` | required | 1,252 | 0 | yes |
| `movies_and_series` | `title` | required | 100 | 0 | yes |
| `movies_and_series` | `universe_id` | required | 100 | 0 | yes |
| `movies_and_series` | `release_year` | required | 100 | 0 | yes |
| `movies_and_series` | `content_type` | required | 100 | 0 | yes |
| `movies_and_series` | `production_studio` | required | 100 | 0 | yes |
| `movies_and_series` | `synopsis` | required | 100 | 0 | yes |
| `movies_and_series` | `continuity` | required | 100 | 0 | yes |
| `comics` | `title` | required | 141 | 0 | yes |
| `comics` | `universe_id` | required | 141 | 0 | yes |
| `comics` | `issue_number` | required | 141 | 0 | yes |
| `comics` | `publication_year` | required | 141 | 0 | yes |
| `comics` | `continuity` | required | 141 | 0 | yes |
| `missions` | `mission_name` | required | 60 | 0 | yes |
| `missions` | `universe_id` | required | 60 | 0 | yes |
| `missions` | `storyline_category` | required | 60 | 0 | yes |
| `missions` | `start_year` | required | 60 | 0 | yes |
| `missions` | `description` | required | 60 | 0 | yes |
| `missions` | `outcome` | required | 60 | 0 | yes |
| `missions` | `continuity` | required | 60 | 0 | yes |
| `character_mission_participation` | `character_id` | required | 264 | 0 | yes |
| `character_mission_participation` | `mission_id` | required | 264 | 0 | yes |
| `character_mission_participation` | `role` | required | 264 | 0 | yes |
| `character_mission_participation` | `outcome` | required | 264 | 0 | yes |
| `character_mission_participation` | `survival_status` | required | 264 | 0 | yes |
| `organizations` | `organization_name` | required | 51 | 0 | yes |
| `organizations` | `universe_id` | required | 51 | 0 | yes |
| `organizations` | `organization_type` | required | 51 | 0 | yes |
| `organizations` | `objectives` | required | 51 | 0 | yes |
| `organizations` | `continuity` | required | 51 | 0 | yes |
| `battles` | `battle_name` | required | 80 | 0 | yes |
| `battles` | `universe_id` | required | 80 | 0 | yes |
| `battles` | `location` | required | 80 | 0 | yes |
| `battles` | `year` | required | 80 | 0 | yes |
| `battles` | `description` | required | 80 | 0 | yes |
| `battles` | `winner` | required | 80 | 0 | yes |
| `battles` | `continuity` | required | 80 | 0 | yes |
| `battle_participation` | `battle_id` | required | 417 | 0 | yes |
| `battle_participation` | `character_id` | required | 417 | 0 | yes |
| `battle_participation` | `side` | required | 417 | 0 | yes |
| `battle_participation` | `battle_result` | required | 417 | 0 | yes |
| `battle_participation` | `status` | required | 417 | 0 | yes |
| `character_relationships` | `character1_id` | required | 188 | 0 | yes |
| `character_relationships` | `character2_id` | required | 188 | 0 | yes |
| `character_relationships` | `relationship_type` | required | 188 | 0 | yes |
| `character_relationships` | `description` | required | 188 | 0 | yes |
| `character_relationships` | `continuity` | required | 188 | 0 | yes |
| `characters` | `real_name` | optional (NULL allowed) | 252 | 0 | yes |
| `characters` | `first_appearance` | optional (NULL allowed) | 252 | 6 | yes |
| `teams` | `founding_year` | optional (NULL allowed) | 36 | 0 | yes |
| `teams` | `headquarters` | optional (NULL allowed) | 36 | 0 | yes |
| `character_team_memberships` | `joining_date` | optional (NULL allowed) | 208 | 0 | yes |
| `character_team_memberships` | `departure_date` | optional (NULL allowed) | 208 | 182 | yes |
| `movies_and_series` | `director` | optional (NULL allowed) | 100 | 5 | yes |
| `movies_and_series` | `duration_minutes` | optional (NULL allowed) | 100 | 0 | yes |
| `movies_and_series` | `rating` | optional (NULL allowed) | 100 | 0 | yes |
| `comics` | `writer` | optional (NULL allowed) | 141 | 0 | yes |
| `comics` | `artist` | optional (NULL allowed) | 141 | 0 | yes |
| `comics` | `storyline` | optional (NULL allowed) | 141 | 0 | yes |
| `comics` | `associated_character_id` | optional (NULL allowed) | 141 | 0 | yes |
| `missions` | `end_year` | optional (NULL allowed) | 60 | 0 | yes |
| `organizations` | `headquarters` | optional (NULL allowed) | 51 | 0 | yes |
| `battles` | `casualties` | optional (NULL allowed) | 80 | 0 | yes |
| `character_power_mapping` | `limitations` | optional (NULL allowed) | 1,252 | 0 | yes |

## Consistency

| Check | Rows examined | Violations |
| --- | ---: | ---: |
| Screen and comic continuity agrees with universe | 241 | 0 |
| Battle combatants are from the battle publisher | 417 | 0 |
| Mission participants share the mission universe | 264 | 0 |
| Membership departure is not before joining | 208 | 0 |
| Mission end year is not before start year | 60 | 0 |
| Relationship pairs are ordered and distinct | 188 | 0 |
| Power level is within 1-10 | 103 | 0 |
| Release year is plausible | 100 | 0 |
| Survival status uses the agreed vocabulary | 264 | 0 |
| Proficiency uses the agreed vocabulary | 1,252 | 0 |
| Original additions are labelled | 252 | 0 |
| Comic character matches the comic publisher | 141 | 0 |

## Files produced

| File | Rows |
| --- | ---: |
| `csv/universes.csv` | 2 |
| `csv/characters.csv` | 252 |
| `csv/teams.csv` | 36 |
| `csv/character_team_memberships.csv` | 208 |
| `csv/powers.csv` | 103 |
| `csv/character_power_mapping.csv` | 1,252 |
| `csv/movies_and_series.csv` | 100 |
| `csv/comics.csv` | 141 |
| `csv/missions.csv` | 60 |
| `csv/character_mission_participation.csv` | 264 |
| `csv/organizations.csv` | 51 |
| `csv/battles.csv` | 80 |
| `csv/battle_participation.csv` | 417 |
| `csv/character_relationships.csv` | 188 |
| `universe.xlsx` | 14 entity sheets + README + Counts |
| `sql_demonstrations.sql` | readable script, 14 queries |
| `sql_demonstrations.md` | 14 queries with the rows they returned |

## Known limitations

Recorded rather than hidden. Each of these is a deliberate trade-off, not an unnoticed defect.

**1. Seven battles in five thin film continuities cast comic-book records.** The Dark Knight Trilogy, X-Men Film Series and Titans Series carry no character rows of their own, so the three Gotham battles, the three X-Men film battles and the Titans Tower assault list the same character in their comic record (`batman`, `wolverine`, `nightwing`, ...). The battle keeps its film continuity, year and result; the character row is the comics one. The alternative, borrowing a body from an unrelated continuity, would have been worse: the `battle_participation` row would then assert something false about both continuities. `scripts/mdu/battle_rosters.py` documents the same decision and `scripts/mdu/roster.py:STANDBY` enforces it.

**2. 102 characters have no battle participation.** Battle rosters are curated by hand from what each story actually shows, so supporting cast members who never fight (reporters, doctors, aides) have no `battle_participation` row. Character stat queries therefore show a real zero rather than a fabricated fight.

**3. Screen character spellings are the screen versions.** `Thanos (MCU)` and `Thanos` are two rows in two continuities on purpose, and the same holds for Batman, Superman and the rest. Anything that counts "characters" has to say which continuity it means, which is why the overview splits the two publishers and the gallery has a query about alias families.

