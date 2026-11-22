# Entity relationship diagram

Rendered version: **er_diagram.svg**. Normalised to 3NF: every non-key column depends on the key, the whole key and nothing but the key. The 14 tables and 19 foreign keys below are exactly what `db/universe_schema.sql` creates.

```
┌─ uni_universe ──────────────────────────────────
│ ◆ universe_id PK
│ · universe_name
│ · publisher
│ · continuity_type
└───────────────────────────────────────────────

┌─ uni_character ─────────────────────────────────
│ ◆ character_id PK
│ · alias
│ ◇ universe_id FK
│ · character_type
│ · alignment
│ · continuity
└───────────────────────────────────────────────

┌─ uni_team ──────────────────────────────────────
│ ◆ team_id PK
│ · team_name
│ ◇ universe_id FK
│ · founding_year
│ · team_status
└───────────────────────────────────────────────

┌─ uni_membership ────────────────────────────────
│ ◆ membership_id PK
│ ◇ character_id FK
│ ◇ team_id FK
│ · joining_date
│ · membership_status
└───────────────────────────────────────────────

┌─ uni_power ─────────────────────────────────────
│ ◆ power_id PK
│ · power_name
│ · category
│ · power_level
└───────────────────────────────────────────────

┌─ uni_character_power ───────────────────────────
│ ◆ mapping_id PK
│ ◇ character_id FK
│ ◇ power_id FK
│ · proficiency_level
└───────────────────────────────────────────────

┌─ uni_content ───────────────────────────────────
│ ◆ content_id PK
│ · title
│ ◇ universe_id FK
│ · release_year
│ · content_type
└───────────────────────────────────────────────

┌─ uni_comic ─────────────────────────────────────
│ ◆ comic_id PK
│ · title
│ ◇ universe_id FK
│ ◇ associated_character_id FK
│ · publication_year
└───────────────────────────────────────────────

┌─ uni_mission ───────────────────────────────────
│ ◆ mission_id PK
│ · mission_name
│ ◇ universe_id FK
│ · storyline_category
└───────────────────────────────────────────────

┌─ uni_mission_participation ─────────────────────
│ ◆ participation_id PK
│ ◇ character_id FK
│ ◇ mission_id FK
│ · role
│ · survival_status
└───────────────────────────────────────────────

┌─ uni_organization ──────────────────────────────
│ ◆ organization_id PK
│ · organization_name
│ ◇ universe_id FK
│ ◇ leader_character_id FK
└───────────────────────────────────────────────

┌─ uni_battle ────────────────────────────────────
│ ◆ battle_id PK
│ · battle_name
│ ◇ universe_id FK
│ · location
│ · winner
└───────────────────────────────────────────────

┌─ uni_battle_participation ──────────────────────
│ ◆ participation_id PK
│ ◇ battle_id FK
│ ◇ character_id FK
│ · side
│ · battle_result
└───────────────────────────────────────────────

┌─ uni_relationship ──────────────────────────────
│ ◆ relationship_id PK
│ ◇ character1_id FK
│ ◇ character2_id FK
│ · relationship_type
│ · continuity
└───────────────────────────────────────────────


Relationships (child → parent):
  uni_universe                   1 : N            uni_character
  uni_universe                   1 : N            uni_team
  uni_universe                   1 : N            uni_content
  uni_universe                   1 : N            uni_comic
  uni_universe                   1 : N            uni_mission
  uni_universe                   1 : N            uni_organization
  uni_universe                   1 : N            uni_battle
  uni_character                  1 : N            uni_membership
  uni_team                       1 : N            uni_membership
  uni_character                  1 : N            uni_character_power
  uni_power                      1 : N            uni_character_power
  uni_character                  1 : N            uni_mission_participation
  uni_mission                    1 : N            uni_mission_participation
  uni_character                  1 : N            uni_battle_participation
  uni_battle                     1 : N            uni_battle_participation
  uni_character                  1 : N (both sides) uni_relationship
  uni_character                  1 : N            uni_comic
  uni_character                  1 : N            uni_organization
```
