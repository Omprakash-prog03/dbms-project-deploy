# Record insertion log — Marvel & DC Universe Database

Run: 2026-11-22T19:13:03 · target: local portal database (SQLite, same repository layer as the deployed instance)

## Batch results

| Entity | Target table | Generated | Inserted | Failed | Skipped | Status |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| universes | `uni_universe` | 2 | 2 | 0 | 0 | verified |
| characters | `uni_character` | 252 | 252 | 0 | 0 | verified |
| teams | `uni_team` | 36 | 36 | 0 | 0 | verified |
| powers | `uni_power` | 103 | 103 | 0 | 0 | verified |
| contents | `uni_content` | 100 | 100 | 0 | 0 | verified |
| comics | `uni_comic` | 141 | 141 | 0 | 0 | verified |
| missions | `uni_mission` | 60 | 60 | 0 | 0 | verified |
| organizations | `uni_organization` | 51 | 51 | 0 | 0 | verified |
| battles | `uni_battle` | 80 | 80 | 0 | 0 | verified |
| memberships | `uni_membership` | 208 | 208 | 0 | 0 | verified |
| character_powers | `uni_character_power` | 1,252 | 1,252 | 0 | 0 | verified |
| mission_participation | `uni_mission_participation` | 264 | 264 | 0 | 0 | verified |
| battle_participation | `uni_battle_participation` | 417 | 417 | 0 | 0 | verified |
| relationships | `uni_relationship` | 188 | 188 | 0 | 0 | verified |

**Totals: 3,154 generated, 3,154 inserted, 0 failed, 0 skipped.**

## Schema application

43 DDL statements applied:

- `table uni_universe`
- `table uni_character`
- `table uni_team`
- `table uni_membership`
- `table uni_power`
- `table uni_character_power`
- `table uni_content`
- `table uni_comic`
- `table uni_mission`
- `table uni_mission_participation`
- `table uni_organization`
- `table uni_battle`
- `table uni_battle_participation`
- `table uni_relationship`
- `index ix_uni_character_universe`
- `index ix_uni_character_alignment`
- `index ix_uni_team_universe`
- `index ix_uni_membership_team`
- `index ix_uni_membership_character`
- `index ix_uni_cp_power`
- `index ix_uni_content_universe`
- `index ix_uni_comic_character`
- `index ix_uni_comic_universe`
- `index ix_uni_mission_universe`
- `index ix_uni_mp_mission`
- `index ix_uni_org_leader`
- `index ix_uni_battle_universe`
- `index ix_uni_bp_character`
- `index ix_uni_rel_character2`
- `view v_uni_character_profile`
- `view v_uni_character_profile`
- `view v_uni_universe_summary`
- `view v_uni_universe_summary`
- `view v_uni_team_roster`
- `view v_uni_team_roster`
- `view v_uni_power_distribution`
- `view v_uni_power_distribution`
- `view v_uni_battle_summary`
- `view v_uni_battle_summary`
- `view v_uni_relationship_network`
- `view v_uni_relationship_network`
- `view v_uni_screen_catalogue`
- `view v_uni_screen_catalogue`

## Post-load verification (read back from the database)

| Table | Expected | In database | Match |
| --- | ---: | ---: | --- |
| `uni_universe` | 2 | 2 | yes |
| `uni_character` | 252 | 252 | yes |
| `uni_team` | 36 | 36 | yes |
| `uni_power` | 103 | 103 | yes |
| `uni_content` | 100 | 100 | yes |
| `uni_comic` | 141 | 141 | yes |
| `uni_mission` | 60 | 60 | yes |
| `uni_organization` | 51 | 51 | yes |
| `uni_battle` | 80 | 80 | yes |
| `uni_membership` | 208 | 208 | yes |
| `uni_character_power` | 1,252 | 1,252 | yes |
| `uni_mission_participation` | 264 | 264 | yes |
| `uni_battle_participation` | 417 | 417 | yes |
| `uni_relationship` | 188 | 188 | yes |

## Post-load foreign-key verification

| Child | Column | Parent | Orphan rows |
| --- | --- | --- | ---: |
| `uni_character` | `universe_id` | `uni_universe` | 0 |
| `uni_team` | `universe_id` | `uni_universe` | 0 |
| `uni_membership` | `character_id` | `uni_character` | 0 |
| `uni_membership` | `team_id` | `uni_team` | 0 |
| `uni_character_power` | `character_id` | `uni_character` | 0 |
| `uni_character_power` | `power_id` | `uni_power` | 0 |
| `uni_content` | `universe_id` | `uni_universe` | 0 |
| `uni_comic` | `universe_id` | `uni_universe` | 0 |
| `uni_comic` | `associated_character_id` | `uni_character` | 0 |
| `uni_mission` | `universe_id` | `uni_universe` | 0 |
| `uni_mission_participation` | `character_id` | `uni_character` | 0 |
| `uni_mission_participation` | `mission_id` | `uni_mission` | 0 |
| `uni_organization` | `universe_id` | `uni_universe` | 0 |
| `uni_organization` | `leader_character_id` | `uni_character` | 0 |
| `uni_battle` | `universe_id` | `uni_universe` | 0 |
| `uni_battle_participation` | `battle_id` | `uni_battle` | 0 |
| `uni_battle_participation` | `character_id` | `uni_character` | 0 |
| `uni_relationship` | `character1_id` | `uni_character` | 0 |
| `uni_relationship` | `character2_id` | `uni_character` | 0 |

## Views

| View | Rows returned |
| --- | ---: |
| `v_uni_character_profile` | 252 |
| `v_uni_universe_summary` | 2 |
| `v_uni_team_roster` | 208 |
| `v_uni_power_distribution` | 103 |
| `v_uni_battle_summary` | 80 |
| `v_uni_relationship_network` | 188 |
| `v_uni_screen_catalogue` | 100 |

## Statement-level log

| Entity | Result | Detail | First error |
| --- | --- | --- | --- |
| reset | applied | dropped and rebuilt the 14 uni_ tables only | — |
| schema | applied | 43 DDL statements (tables + views) | — |
| universes | inserted | 2/2 rows into uni_universe | — |
| characters | inserted | 252/252 rows into uni_character | — |
| teams | inserted | 36/36 rows into uni_team | — |
| powers | inserted | 103/103 rows into uni_power | — |
| contents | inserted | 100/100 rows into uni_content | — |
| comics | inserted | 141/141 rows into uni_comic | — |
| missions | inserted | 60/60 rows into uni_mission | — |
| organizations | inserted | 51/51 rows into uni_organization | — |
| battles | inserted | 80/80 rows into uni_battle | — |
| memberships | inserted | 208/208 rows into uni_membership | — |
| character_powers | inserted | 1252/1252 rows into uni_character_power | — |
| mission_participation | inserted | 264/264 rows into uni_mission_participation | — |
| battle_participation | inserted | 417/417 rows into uni_battle_participation | — |
| relationships | inserted | 188/188 rows into uni_relationship | — |
