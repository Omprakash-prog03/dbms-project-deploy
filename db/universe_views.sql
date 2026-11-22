-- ============================================================================
-- MARVEL & DC UNIVERSE DATABASE MANAGEMENT SYSTEM (MDU)
-- Reporting views. Every view is a single SELECT over the 14 uni_ tables, so it
-- is the same statement on MySQL 8 and on the portal's embedded engine.
-- ============================================================================

-- 1. Character card: universe, alignment, team count, power count, best power.
CREATE OR REPLACE VIEW v_uni_character_profile AS
SELECT
    c.character_id,
    c.alias,
    COALESCE(c.real_name, 'Unknown')            AS real_name,
    u.universe_name,
    c.character_type,
    c.alignment,
    c.species,
    c.current_status,
    c.continuity,
    (SELECT COUNT(*) FROM uni_membership m
       WHERE m.character_id = c.character_id)   AS team_count,
    (SELECT COUNT(*) FROM uni_character_power p
       WHERE p.character_id = c.character_id)   AS power_count,
    (SELECT MAX(pw.power_level) FROM uni_character_power p
       JOIN uni_power pw ON pw.power_id = p.power_id
      WHERE p.character_id = c.character_id)    AS top_power_level
FROM uni_character c
JOIN uni_universe u ON u.universe_id = c.universe_id;

-- 2. Universe comparison: head-count and content volume side by side.
CREATE OR REPLACE VIEW v_uni_universe_summary AS
SELECT
    u.universe_id,
    u.universe_name,
    u.publisher,
    u.continuity_type,
    (SELECT COUNT(*) FROM uni_character c WHERE c.universe_id = u.universe_id)      AS characters,
    (SELECT COUNT(*) FROM uni_team t WHERE t.universe_id = u.universe_id)           AS teams,
    (SELECT COUNT(*) FROM uni_content ct WHERE ct.universe_id = u.universe_id)      AS screen_titles,
    (SELECT COUNT(*) FROM uni_comic cm WHERE cm.universe_id = u.universe_id)        AS comics,
    (SELECT COUNT(*) FROM uni_mission mi WHERE mi.universe_id = u.universe_id)      AS missions,
    (SELECT COUNT(*) FROM uni_organization o WHERE o.universe_id = u.universe_id)   AS organizations,
    (SELECT COUNT(*) FROM uni_battle b WHERE b.universe_id = u.universe_id)         AS battles
FROM uni_universe u;

-- 3. Team roster: one row per membership with who and what role.
CREATE OR REPLACE VIEW v_uni_team_roster AS
SELECT
    t.team_id,
    t.team_name,
    u.universe_name,
    t.team_status,
    c.character_id,
    c.alias,
    m.role,
    m.joining_date,
    m.departure_date,
    m.membership_status
FROM uni_team t
JOIN uni_universe u ON u.universe_id = t.universe_id
JOIN uni_membership m ON m.team_id = t.team_id
JOIN uni_character c ON c.character_id = m.character_id;

-- 4. Power distribution: how often each power is held and by whom.
CREATE OR REPLACE VIEW v_uni_power_distribution AS
SELECT
    p.power_id,
    p.power_name,
    p.category,
    p.power_level,
    (SELECT COUNT(*) FROM uni_character_power cp WHERE cp.power_id = p.power_id) AS holders,
    (SELECT COUNT(*) FROM uni_character_power cp
       JOIN uni_character c ON c.character_id = cp.character_id
      WHERE cp.power_id = p.power_id AND c.character_type = 'Hero')              AS heroes,
    (SELECT COUNT(*) FROM uni_character_power cp
       JOIN uni_character c ON c.character_id = cp.character_id
      WHERE cp.power_id = p.power_id AND c.character_type = 'Villain')           AS villains
FROM uni_power p;

-- 5. Battle card with participation volume and dead/alive split.
CREATE OR REPLACE VIEW v_uni_battle_summary AS
SELECT
    b.battle_id,
    b.battle_name,
    u.universe_name,
    b.location,
    b.year,
    b.winner,
    b.casualties,
    (SELECT COUNT(*) FROM uni_battle_participation bp WHERE bp.battle_id = b.battle_id) AS combatants,
    (SELECT COUNT(*) FROM uni_battle_participation bp
      WHERE bp.battle_id = b.battle_id AND bp.status <> 'Survived')                     AS losses
FROM uni_battle b
JOIN uni_universe u ON u.universe_id = b.universe_id;

-- 6. Relationship network: the pair, typed, with both aliases resolved.
CREATE OR REPLACE VIEW v_uni_relationship_network AS
SELECT
    r.relationship_id,
    c1.alias                AS character_1,
    c2.alias                AS character_2,
    r.relationship_type,
    r.continuity,
    u1.universe_name,
    CASE WHEN c1.universe_id = c2.universe_id THEN 'Same universe'
         ELSE 'Cross-universe' END AS pair_scope
FROM uni_relationship r
JOIN uni_character c1 ON c1.character_id = r.character1_id
JOIN uni_character c2 ON c2.character_id = r.character2_id
JOIN uni_universe u1 ON u1.universe_id = c1.universe_id;

-- 7. Screen catalogue: films and series by universe and year.
CREATE OR REPLACE VIEW v_uni_screen_catalogue AS
SELECT
    ct.content_id,
    ct.title,
    u.universe_name,
    ct.release_year,
    ct.content_type,
    ct.director,
    ct.production_studio,
    ct.duration_minutes,
    ct.rating,
    ct.continuity
FROM uni_content ct
JOIN uni_universe u ON u.universe_id = ct.universe_id;
