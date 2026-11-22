-- SQL demonstrations — Marvel & DC Universe Database
-- Generated 2026-11-22 by scripts/build_universe_dataset.py
-- Every statement below is read-only and matches the gallery at /universe/sql.
-- Load the data first:  sqlite3 sims_embedded.db < datasets/sql/load_universe.sql
-- Scroll to the end of each block for the rows the statement actually returned.
-- ==========================================================================
-- 1. All Marvel heroes with more than four powers
-- INNER JOIN + GROUP BY + HAVING. Answers "which Marvel heroes are the most versatile?"
-- ==========================================================================
SELECT c.alias, c.character_type, COUNT(cp.power_id) AS powers
FROM uni_character c
JOIN uni_universe u ON u.universe_id = c.universe_id
JOIN uni_character_power cp ON cp.character_id = c.character_id
WHERE u.universe_name = 'Marvel' AND c.alignment = 'Good'
GROUP BY c.character_id, c.alias, c.character_type
HAVING COUNT(cp.power_id) > 4
ORDER BY powers DESC, c.alias;

-- 77 row(s) returned


-- ==========================================================================
-- 2. Universe comparison
-- Aggregate functions over correlated subqueries: one row per publisher.
-- ==========================================================================
SELECT universe_name, characters, teams, screen_titles, comics, missions, battles
FROM v_uni_universe_summary
ORDER BY characters DESC;

-- 2 row(s) returned


-- ==========================================================================
-- 3. Teams with no current members
-- LEFT JOIN + IS NULL, the classic anti-join.
-- ==========================================================================
SELECT t.team_name, u.universe_name, COUNT(m.membership_id) AS ever_members
FROM uni_team t
JOIN uni_universe u ON u.universe_id = t.universe_id
LEFT JOIN uni_membership m ON m.team_id = t.team_id
 AND m.membership_status = 'Current'
WHERE m.membership_id IS NULL
GROUP BY t.team_id, t.team_name, u.universe_name
ORDER BY ever_members DESC;

-- 1 row(s) returned


-- ==========================================================================
-- 4. Character statistics, ranked
-- Nested query + ORDER BY: the busiest characters across every mapping table.
-- ==========================================================================
SELECT c.alias, u.universe_name,
       (SELECT COUNT(*) FROM uni_membership m WHERE m.character_id = c.character_id) AS teams,
       (SELECT COUNT(*) FROM uni_character_power p WHERE p.character_id = c.character_id) AS powers,
       (SELECT COUNT(*) FROM uni_mission_participation q WHERE q.character_id = c.character_id) AS missions,
       (SELECT COUNT(*) FROM uni_battle_participation b WHERE b.character_id = c.character_id) AS battles
FROM uni_character c
JOIN uni_universe u ON u.universe_id = c.universe_id
ORDER BY battles DESC, missions DESC, powers DESC
LIMIT 12;

-- 12 row(s) returned


-- ==========================================================================
-- 5. Power distribution by category
-- GROUP BY + HAVING + aggregate over a view.
-- ==========================================================================
SELECT category, COUNT(*) AS powers, SUM(holders) AS total_holders,
       ROUND(AVG(power_level), 2) AS average_level
FROM v_uni_power_distribution
GROUP BY category
HAVING SUM(holders) > 5
ORDER BY total_holders DESC;

-- 9 row(s) returned


-- ==========================================================================
-- 6. Villains who win battles
-- Correlated subquery in FROM plus GROUP BY: does evil ever actually win here?
-- ==========================================================================
SELECT c.alias AS villain, u.universe_name,
       (SELECT COUNT(*) FROM uni_battle_participation p
         WHERE p.character_id = c.character_id AND p.battle_result = 'Victorious') AS battles_won,
       (SELECT COUNT(*) FROM uni_battle_participation p
         WHERE p.character_id = c.character_id) AS battles_fought
FROM (SELECT character_id FROM uni_character WHERE alignment = 'Evil') evil
JOIN uni_character c ON c.character_id = evil.character_id
JOIN uni_universe u ON u.universe_id = c.universe_id
WHERE battles_won > 0
GROUP BY c.character_id, c.alias, u.universe_name
ORDER BY battles_won DESC, battles_fought DESC, c.alias;

-- 13 row(s) returned


-- ==========================================================================
-- 7. Battles by decade and universe
-- GROUP BY on a computed expression.
-- ==========================================================================
SELECT (year / 10) * 10 AS decade, u.universe_name, COUNT(*) AS battles,
       SUM(CASE WHEN casualties IS NULL THEN 0 ELSE casualties END) AS casualties
FROM uni_battle b
JOIN uni_universe u ON u.universe_id = b.universe_id
GROUP BY (year / 10) * 10, u.universe_name
ORDER BY decade, u.universe_name;

-- 12 row(s) returned


-- ==========================================================================
-- 8. Relationship network density
-- Self-join on the character table through the relationship table.
-- ==========================================================================
SELECT c.alias, COUNT(*) AS relationships
FROM uni_relationship r
JOIN uni_character c ON c.character_id = r.character1_id
GROUP BY c.character_id, c.alias
HAVING COUNT(*) >= 3
ORDER BY relationships DESC;

-- 15 row(s) returned


-- ==========================================================================
-- 9. Screen catalogue by continuity
-- Distinguishes the adaptations the brief asks to keep separate.
-- ==========================================================================
SELECT continuity, content_type, COUNT(*) AS titles,
       MIN(release_year) AS first_year, MAX(release_year) AS last_year
FROM uni_content
GROUP BY continuity, content_type
ORDER BY titles DESC;

-- 24 row(s) returned


-- ==========================================================================
-- 10. Comic decades by publisher
-- GROUP BY + aggregate on a view-free query.
-- ==========================================================================
SELECT (publication_year / 10) * 10 AS decade, u.universe_name, COUNT(*) AS issues
FROM uni_comic cm
JOIN uni_universe u ON u.universe_id = cm.universe_id
GROUP BY (publication_year / 10) * 10, u.universe_name
ORDER BY decade, u.universe_name;

-- 14 row(s) returned


-- ==========================================================================
-- 11. Missions with the heaviest losses
-- Nested query with a correlated aggregate and a HAVING clause.
-- ==========================================================================
SELECT m.mission_name, m.start_year, u.universe_name, COUNT(p.participation_id) AS participants,
       SUM(CASE WHEN p.survival_status = 'Killed' THEN 1 ELSE 0 END) AS killed
FROM uni_mission m
JOIN uni_universe u ON u.universe_id = m.universe_id
JOIN uni_mission_participation p ON p.mission_id = m.mission_id
GROUP BY m.mission_id, m.mission_name, m.start_year, u.universe_name
HAVING SUM(CASE WHEN p.survival_status = 'Killed' THEN 1 ELSE 0 END) > 0
ORDER BY killed DESC, participants DESC;

-- 26 row(s) returned


-- ==========================================================================
-- 12. Characters who lead an organisation
-- LEFT JOIN from the child side, with a NULL check.
-- ==========================================================================
SELECT o.organization_name, o.organization_type, c.alias AS leader,
       c.character_type, u.universe_name
FROM uni_organization o
JOIN uni_universe u ON u.universe_id = o.universe_id
LEFT JOIN uni_character c ON c.character_id = o.leader_character_id
ORDER BY u.universe_name, o.organization_name;

-- 51 row(s) returned


-- ==========================================================================
-- 13. Cross-universe characters (same alias family)
-- Shows how the comic and screen records are kept apart rather than merged.
-- ==========================================================================
SELECT alias, continuity, character_type, current_status
FROM uni_character
WHERE alias LIKE '%(MCU)%' OR alias LIKE '%(DCEU)%'
ORDER BY alias;

-- 51 row(s) returned


-- ==========================================================================
-- 14. Every table, one row count
-- UNION ALL over literal selects: the row-count ledger for the viva.
-- ==========================================================================
SELECT 'uni_universe' AS table_name, COUNT(*) AS rows FROM uni_universe
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
ORDER BY table_name;

-- 14 row(s) returned
