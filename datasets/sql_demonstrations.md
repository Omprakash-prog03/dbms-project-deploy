# SQL demonstration queries

Generated 2026-11-22 against the loaded database. Each query below was executed against the live tables; the table under it is what came back, not an example.

The same statements are in `datasets/sql_demonstrations.sql` (runnable) and in the portal at **Marvel & DC Universe → SQL gallery** (`/universe/sql`), where they run read-only and any logged-in user can step through them.

| # | Query | Technique | Rows |
| ---: | --- | --- | ---: |
| 1 | All Marvel heroes with more than four powers | INNER JOIN + GROUP BY + HAVING. Answers "which Marvel heroes are the most versatile?" | 77 |
| 2 | Universe comparison | Aggregate functions over correlated subqueries: one row per publisher. | 2 |
| 3 | Teams with no current members | LEFT JOIN + IS NULL, the classic anti-join. | 1 |
| 4 | Character statistics, ranked | Nested query + ORDER BY: the busiest characters across every mapping table. | 12 |
| 5 | Power distribution by category | GROUP BY + HAVING + aggregate over a view. | 9 |
| 6 | Villains who win battles | Correlated subquery in FROM plus GROUP BY: does evil ever actually win here? | 13 |
| 7 | Battles by decade and universe | GROUP BY on a computed expression. | 12 |
| 8 | Relationship network density | Self-join on the character table through the relationship table. | 15 |
| 9 | Screen catalogue by continuity | Distinguishes the adaptations the brief asks to keep separate. | 24 |
| 10 | Comic decades by publisher | GROUP BY + aggregate on a view-free query. | 14 |
| 11 | Missions with the heaviest losses | Nested query with a correlated aggregate and a HAVING clause. | 26 |
| 12 | Characters who lead an organisation | LEFT JOIN from the child side, with a NULL check. | 51 |
| 13 | Cross-universe characters (same alias family) | Shows how the comic and screen records are kept apart rather than merged. | 51 |
| 14 | Every table, one row count | UNION ALL over literal selects: the row-count ledger for the viva. | 14 |

## 1. All Marvel heroes with more than four powers

INNER JOIN + GROUP BY + HAVING. Answers "which Marvel heroes are the most versatile?"

```sql
SELECT c.alias, c.character_type, COUNT(cp.power_id) AS powers
FROM uni_character c
JOIN uni_universe u ON u.universe_id = c.universe_id
JOIN uni_character_power cp ON cp.character_id = c.character_id
WHERE u.universe_name = 'Marvel' AND c.alignment = 'Good'
GROUP BY c.character_id, c.alias, c.character_type
HAVING COUNT(cp.power_id) > 4
ORDER BY powers DESC, c.alias
```

| alias | character_type | powers |
| --- | --- | --- |
| Adam Warlock | Hero | 5 |
| Ant-Man | Hero | 5 |
| Antares | Hero | 5 |
| Beast | Supporting | 5 |
| Black Bolt | Hero | 5 |
| Black Panther | Hero | 5 |
| Black Panther (MCU) | Hero | 5 |
| Black Widow | Hero | 5 |
| Black Widow (MCU) | Hero | 5 |
| Blade | Antihero | 5 |
| Captain America | Hero | 5 |
| Captain America (MCU) | Hero | 5 |
| Captain Marvel | Hero | 5 |
| Captain Marvel (MCU) | Hero | 5 |
| Cloak | Hero | 5 |
| Crystal | Hero | 5 |
| Cyclops | Hero | 5 |
| Dagger | Hero | 5 |
| Daredevil | Hero | 5 |
| Daredevil (MCU) | Hero | 5 |
| Doctor Strange | Hero | 5 |
| Doctor Strange (MCU) | Hero | 5 |
| Falcon | Hero | 5 |
| Falcon (MCU) | Hero | 5 |
| Gambit | Hero | 5 |
| Gorgon | Supporting | 5 |
| Groot | Hero | 5 |
| Groot (MCU) | Hero | 5 |
| Hawkeye | Hero | 5 |
| Hawkeye (MCU) | Hero | 5 |
| Hulk | Hero | 5 |
| Hulk (MCU) | Hero | 5 |
| Human Torch | Hero | 5 |
| Invisible Woman | Hero | 5 |
| Iron Fist | Hero | 5 |
| Iron Fist (MCU) | Hero | 5 |
| Iron Man | Hero | 5 |
| Iron Man (MCU) | Hero | 5 |
| Jean Grey | Hero | 5 |
| Karnak | Supporting | 5 |
| Luke Cage | Hero | 5 |
| Luke Cage (MCU) | Hero | 5 |
| Mantis | Hero | 5 |
| Mantis (MCU) | Hero | 5 |
| Medusa | Hero | 5 |
| Mister Fantastic | Hero | 5 |
| Ms. Marvel (Earth-616) | Hero | 5 |
| Nick Fury | Supporting | 5 |
| Nick Fury (MCU) | Supporting | 5 |
| Nightcrawler | Hero | 5 |
| Nova | Hero | 5 |
| Phil Coulson | Supporting | 5 |
| Professor X | Supporting | 5 |
| Rocket (MCU) | Hero | 5 |
| Rocket Raccoon | Hero | 5 |
| Rogue | Hero | 5 |
| Scarlet Witch | Hero | 5 |
| Scarlet Witch (MCU) | Hero | 5 |
| Shadowcat | Hero | 5 |
| Silver Surfer | Hero | 5 |
| Spider-Gwen | Hero | 5 |
| Spider-Man | Hero | 5 |
| Spider-Man (MCU) | Hero | 5 |
| Spider-Man (Miles Morales) | Hero | 5 |
| Star-Lord | Hero | 5 |
| Star-Lord (MCU) | Hero | 5 |
| Storm | Hero | 5 |
| The Ancient One | Supporting | 5 |
| Thor | Hero | 5 |
| Thor (MCU) | Hero | 5 |
| Vision | Hero | 5 |
| Vision (MCU) | Hero | 5 |
| War Machine | Hero | 5 |
| War Machine (MCU) | Hero | 5 |
| Wasp | Hero | 5 |
| Wolverine | Hero | 5 |
| Wong | Supporting | 5 |

## 2. Universe comparison

Aggregate functions over correlated subqueries: one row per publisher.

```sql
SELECT universe_name, characters, teams, screen_titles, comics, missions, battles
FROM v_uni_universe_summary
ORDER BY characters DESC
```

| universe_name | characters | teams | screen_titles | comics | missions | battles |
| --- | --- | --- | --- | --- | --- | --- |
| Marvel | 147 | 18 | 65 | 57 | 30 | 43 |
| DC | 105 | 18 | 35 | 84 | 30 | 37 |

## 3. Teams with no current members

LEFT JOIN + IS NULL, the classic anti-join.

```sql
SELECT t.team_name, u.universe_name, COUNT(m.membership_id) AS ever_members
FROM uni_team t
JOIN uni_universe u ON u.universe_id = t.universe_id
LEFT JOIN uni_membership m ON m.team_id = t.team_id
 AND m.membership_status = 'Current'
WHERE m.membership_id IS NULL
GROUP BY t.team_id, t.team_name, u.universe_name
ORDER BY ever_members DESC
```

| team_name | universe_name | ever_members |
| --- | --- | --- |
| SHIELD (MCU) | Marvel | 0 |

## 4. Character statistics, ranked

Nested query + ORDER BY: the busiest characters across every mapping table.

```sql
SELECT c.alias, u.universe_name,
       (SELECT COUNT(*) FROM uni_membership m WHERE m.character_id = c.character_id) AS teams,
       (SELECT COUNT(*) FROM uni_character_power p WHERE p.character_id = c.character_id) AS powers,
       (SELECT COUNT(*) FROM uni_mission_participation q WHERE q.character_id = c.character_id) AS missions,
       (SELECT COUNT(*) FROM uni_battle_participation b WHERE b.character_id = c.character_id) AS battles
FROM uni_character c
JOIN uni_universe u ON u.universe_id = c.universe_id
ORDER BY battles DESC, missions DESC, powers DESC
LIMIT 12
```

| alias | universe_name | teams | powers | missions | battles |
| --- | --- | --- | --- | --- | --- |
| Green Lantern | DC | 2 | 5 | 4 | 11 |
| Batman | DC | 2 | 6 | 16 | 10 |
| Superman | DC | 1 | 5 | 8 | 9 |
| Captain America (MCU) | Marvel | 1 | 5 | 3 | 9 |
| Scarlet Witch (MCU) | Marvel | 1 | 5 | 2 | 9 |
| The Flash | DC | 1 | 5 | 6 | 8 |
| Hulk (MCU) | Marvel | 1 | 5 | 3 | 8 |
| Wonder Woman | DC | 2 | 5 | 7 | 6 |
| Wolverine | Marvel | 1 | 5 | 5 | 6 |
| Cyclops | Marvel | 1 | 5 | 3 | 6 |
| Thor (MCU) | Marvel | 1 | 5 | 3 | 6 |
| Thanos (MCU) | Marvel | 0 | 5 | 3 | 6 |

## 5. Power distribution by category

GROUP BY + HAVING + aggregate over a view.

```sql
SELECT category, COUNT(*) AS powers, SUM(holders) AS total_holders,
       ROUND(AVG(power_level), 2) AS average_level
FROM v_uni_power_distribution
GROUP BY category
HAVING SUM(holders) > 5
ORDER BY total_holders DESC
```

| category | powers | total_holders | average_level |
| --- | --- | --- | --- |
| Physical | 21 | 391 | 5.95 |
| Combat skill | 8 | 222 | 4.5 |
| Intellect | 11 | 202 | 4.73 |
| Mental | 15 | 184 | 6.07 |
| Energy | 14 | 90 | 6.86 |
| Technological | 6 | 47 | 5.5 |
| Biological | 11 | 44 | 5.0 |
| Mystical | 8 | 40 | 7.0 |
| Cosmic | 9 | 32 | 8.78 |

## 6. Villains who win battles

Correlated subquery in FROM plus GROUP BY: does evil ever actually win here?

```sql
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
ORDER BY battles_won DESC, battles_fought DESC, c.alias
```

| villain | universe_name | battles_won | battles_fought |
| --- | --- | --- | --- |
| Thanos (MCU) | Marvel | 3 | 6 |
| Loki | Marvel | 2 | 4 |
| Bane | DC | 2 | 2 |
| Brainiac | DC | 1 | 3 |
| Darkseid | DC | 1 | 3 |
| Magneto | Marvel | 1 | 3 |
| Deathstroke | DC | 1 | 2 |
| Ebony Maw | Marvel | 1 | 1 |
| Hela | Marvel | 1 | 1 |
| Killmonger | Marvel | 1 | 1 |
| Nebula | Marvel | 1 | 1 |
| Ra's al Ghul | DC | 1 | 1 |
| Talia al Ghul | DC | 1 | 1 |

## 7. Battles by decade and universe

GROUP BY on a computed expression.

```sql
SELECT (year / 10) * 10 AS decade, u.universe_name, COUNT(*) AS battles,
       SUM(CASE WHEN casualties IS NULL THEN 0 ELSE casualties END) AS casualties
FROM uni_battle b
JOIN uni_universe u ON u.universe_id = b.universe_id
GROUP BY (year / 10) * 10, u.universe_name
ORDER BY decade, u.universe_name
```

| decade | universe_name | battles | casualties |
| --- | --- | --- | --- |
| 1960 | Marvel | 1 | 0 |
| 1970 | DC | 1 | 0 |
| 1980 | DC | 2 | 0 |
| 1980 | Marvel | 3 | 1 |
| 1990 | DC | 4 | 0 |
| 1990 | Marvel | 1 | 0 |
| 2000 | DC | 7 | 0 |
| 2000 | Marvel | 7 | 16000000 |
| 2010 | DC | 21 | 5013 |
| 2010 | Marvel | 22 | 701 |
| 2020 | DC | 2 | 0 |
| 2020 | Marvel | 9 | 1 |

## 8. Relationship network density

Self-join on the character table through the relationship table.

```sql
SELECT c.alias, COUNT(*) AS relationships
FROM uni_relationship r
JOIN uni_character c ON c.character_id = r.character1_id
GROUP BY c.character_id, c.alias
HAVING COUNT(*) >= 3
ORDER BY relationships DESC
```

| alias | relationships |
| --- | --- |
| Batman | 19 |
| Spider-Man | 12 |
| Superman | 12 |
| Wolverine | 5 |
| Iron Man | 4 |
| The Flash | 4 |
| Wonder Woman | 4 |
| Aquaman (DCEU) | 3 |
| Batgirl | 3 |
| Daredevil | 3 |
| Green Lantern | 3 |
| Harley Quinn (DCEU) | 3 |
| Mystique | 3 |
| Superman (DCEU) | 3 |
| Thanos | 3 |

## 9. Screen catalogue by continuity

Distinguishes the adaptations the brief asks to keep separate.

```sql
SELECT continuity, content_type, COUNT(*) AS titles,
       MIN(release_year) AS first_year, MAX(release_year) AS last_year
FROM uni_content
GROUP BY continuity, content_type
ORDER BY titles DESC
```

| continuity | content_type | titles | first_year | last_year |
| --- | --- | --- | --- | --- |
| Marvel Cinematic Universe (Earth-199999) | Film | 35 | 2008 | 2025 |
| DCEU (Earth-1) | Film | 15 | 2013 | 2023 |
| Marvel Cinematic Universe (Earth-199999) | Television series | 15 | 2013 | 2023 |
| DC Comics (Arrowverse) | Television series | 5 | 2012 | 2021 |
| Marvel Comics (X-Men Film Series) | Film | 4 | 2000 | 2017 |
| DC Comics (Dark Knight Trilogy) | Film | 3 | 2005 | 2012 |
| DC Comics (DCAU) | Animated series | 2 | 1992 | 2001 |
| DC Comics (Titans Series) | Television series | 2 | 2018 | 2019 |
| DC Comics (Vertigo) | Film | 2 | 2005 | 2009 |
| Marvel Comics (Raimi Film Series) | Film | 2 | 2002 | 2004 |
| Marvel Comics (Spider-Man Animation) | Animated series | 2 | 1967 | 1994 |
| DC Comics (1978 Film Series) | Film | 1 | 1978 | 1978 |
| DC Comics (Burton Film Series) | Film | 1 | 1989 | 1989 |
| DC Comics (DCEU) | Television series | 1 | 2022 | 2022 |
| DC Comics (Joker Film Series) | Film | 1 | 2019 | 2019 |
| DC Comics (Reeves Film Series) | Film | 1 | 2022 | 2022 |
| DC Comics (Smallville continuity) | Television series | 1 | 2001 | 2001 |
| Marvel Cinematic Universe (Earth-199999) | Television special | 1 | 2022 | 2022 |
| Marvel Comics (Avengers Animation) | Animated series | 1 | 2010 | 2010 |
| Marvel Comics (Blade Film Series) | Film | 1 | 1998 | 1998 |
| Marvel Comics (Fantastic Four Film Series) | Film | 1 | 2005 | 2005 |
| Marvel Comics (Spider-Man Universe) | Film | 1 | 2018 | 2018 |
| Marvel Comics (Spider-Verse) | Animated film | 1 | 2018 | 2018 |
| Marvel Comics (X-Men Animation) | Animated series | 1 | 1992 | 1992 |

## 10. Comic decades by publisher

GROUP BY + aggregate on a view-free query.

```sql
SELECT (publication_year / 10) * 10 AS decade, u.universe_name, COUNT(*) AS issues
FROM uni_comic cm
JOIN uni_universe u ON u.universe_id = cm.universe_id
GROUP BY (publication_year / 10) * 10, u.universe_name
ORDER BY decade, u.universe_name
```

| decade | universe_name | issues |
| --- | --- | --- |
| 1930 | DC | 2 |
| 1940 | DC | 17 |
| 1950 | DC | 7 |
| 1960 | DC | 12 |
| 1960 | Marvel | 22 |
| 1970 | DC | 3 |
| 1970 | Marvel | 15 |
| 1980 | DC | 21 |
| 1980 | Marvel | 11 |
| 1990 | DC | 7 |
| 1990 | Marvel | 4 |
| 2000 | DC | 10 |
| 2000 | Marvel | 5 |
| 2010 | DC | 5 |

## 11. Missions with the heaviest losses

Nested query with a correlated aggregate and a HAVING clause.

```sql
SELECT m.mission_name, m.start_year, u.universe_name, COUNT(p.participation_id) AS participants,
       SUM(CASE WHEN p.survival_status = 'Killed' THEN 1 ELSE 0 END) AS killed
FROM uni_mission m
JOIN uni_universe u ON u.universe_id = m.universe_id
JOIN uni_mission_participation p ON p.mission_id = m.mission_id
GROUP BY m.mission_id, m.mission_name, m.start_year, u.universe_name
HAVING SUM(CASE WHEN p.survival_status = 'Killed' THEN 1 ELSE 0 END) > 0
ORDER BY killed DESC, participants DESC
```

| mission_name | start_year | universe_name | participants | killed |
| --- | --- | --- | --- | --- |
| The Black Order Assault | 2018 | Marvel | 5 | 4 |
| Flashpoint | 2011 | DC | 5 | 4 |
| The Infinity Saga | 2008 | Marvel | 7 | 3 |
| Avengers: Endgame | 2019 | Marvel | 6 | 3 |
| X-Men: The Dark Phoenix | 2006 | Marvel | 5 | 3 |
| Days of Future Past | 1981 | Marvel | 4 | 3 |
| Avengers: Infinity War | 2018 | Marvel | 6 | 2 |
| Crisis on Infinite Earths | 1985 | DC | 6 | 2 |
| Age of Apocalypse | 1995 | Marvel | 5 | 2 |
| The Death of Superman | 1992 | DC | 4 | 2 |
| The Steppenwolf Invasion | 2017 | DC | 7 | 1 |
| Civil War | 2006 | Marvel | 5 | 1 |
| House of M | 2005 | Marvel | 5 | 1 |
| Siege of Asgard | 2010 | Marvel | 5 | 1 |
| The Hand War | 2017 | Marvel | 5 | 1 |
| The Darkseid War | 2015 | DC | 5 | 1 |
| The Dark Phoenix Saga | 1980 | Marvel | 4 | 1 |
| Secret Invasion | 2008 | Marvel | 4 | 1 |
| Dark Reign | 2008 | Marvel | 4 | 1 |
| Thor: Ragnarok | 2017 | Marvel | 4 | 1 |
| The Westview Anomaly | 2021 | Marvel | 4 | 1 |
| Secret Wars (2015) | 2015 | Marvel | 4 | 1 |
| The Dark Knight Returns | 1986 | DC | 4 | 1 |
| The Kang Dynasty | 2023 | Marvel | 4 | 1 |
| A Death in the Family | 1988 | DC | 3 | 1 |
| The Battle of Metropolis | 2013 | DC | 3 | 1 |

## 12. Characters who lead an organisation

LEFT JOIN from the child side, with a NULL check.

```sql
SELECT o.organization_name, o.organization_type, c.alias AS leader,
       c.character_type, u.universe_name
FROM uni_organization o
JOIN uni_universe u ON u.universe_id = o.universe_id
LEFT JOIN uni_character c ON c.character_id = o.leader_character_id
ORDER BY u.universe_name, o.organization_name
```

| organization_name | organization_type | leader | character_type | universe_name |
| --- | --- | --- | --- | --- |
| A.R.G.U.S. | Government agency | Amanda Waller | Supporting | DC |
| A.R.G.U.S. (DCEU) | Government agency | Amanda Waller (DCEU) | Supporting | DC |
| Apokolips | Cosmic tyranny | Darkseid | Villain | DC |
| Apokolips (DCEU) | Cosmic tyranny | Darkseid | Villain | DC |
| Arkham Asylum | Psychiatric institution | Hugo Strange | Villain | DC |
| Atlantis (DCEU) | Nation state | Aquaman (DCEU) | Hero | DC |
| Birds of Prey | Independent investigative unit | Batgirl | Hero | DC |
| Blue Lantern Circle | Relief corps | Lumen | Supporting | DC |
| Cadmus Project | Black research programme | Amanda Waller | Supporting | DC |
| Checkmate | Intelligence agency | Amanda Waller | Supporting | DC |
| Court of Owls | Secret society | Lincoln March | Villain | DC |
| Daily Planet | News organisation | Perry White | Supporting | DC |
| Gotham City Police Department | Police department | James Gordon | Supporting | DC |
| Green Lantern Corps | Cosmic police (will) | Green Lantern | Hero | DC |
| Kryptonian Science Council | Planetary government | Jor-El | Supporting | DC |
| League of Assassins | Assassin cult | Ra's al Ghul | Villain | DC |
| Legion of Doom | Villain coalition | Lex Luthor | Villain | DC |
| LexCorp | Conglomerate | Lex Luthor | Villain | DC |
| S.T.A.R. Labs | Research laboratory | Cyborg (DCEU) | Hero | DC |
| S.T.A.R. Labs (Arrowverse) | Research laboratory | Felicity Smoak | Supporting | DC |
| Sinestro Corps | Cosmic police (fear) | Sinestro | Villain | DC |
| Stagg Industries | Conglomerate | Lex Luthor | Villain | DC |
| Task Force X | Covert operations unit | Amanda Waller | Supporting | DC |
| Team Arrow | Vigilante cell | Green Arrow (Arrow) | Hero | DC |
| Wayne Enterprises | Conglomerate | Batman | Hero | DC |
| Wayne Enterprises (DCEU) | Conglomerate | Batman (DCEU) | Hero | DC |
| A.I.M. | Scientific collective | Taskmaster | Villain | Marvel |
| Alchemax | Megacorporation | Green Goblin | Villain | Marvel |
| Asgard | Cosmic monarchy | Thor | Hero | Marvel |
| Atlas Foundation | Private research foundation | Antares | Hero | Marvel |
| Brotherhood of Evil Mutants | Mutant supremacy movement | Magneto | Villain | Marvel |
| Daily Bugle | News organisation | J. Jonah Jameson | Supporting | Marvel |
| Fisk Enterprises | Criminal enterprise | Kingpin | Villain | Marvel |
| HYDRA | Terrorist organisation | Red Skull | Villain | Marvel |
| HYDRA (MCU) | Terrorist organisation | Red Skull (MCU) | Villain | Marvel |
| Hellfire Club | Secret society | Emma Frost | Antihero | Marvel |
| Kamar-Taj | Mystical order | Doctor Strange | Hero | Marvel |
| Kamar-Taj (MCU) | Mystical order | Doctor Strange (MCU) | Hero | Marvel |
| Masters of the Mystic Arts | Mystical order | Wong | Supporting | Marvel |
| Nova Corps | Interstellar police | Nova | Hero | Marvel |
| Ravagers | Pirate syndicate | Yondu | Antihero | Marvel |
| Ravagers (MCU) | Pirate syndicate | Yondu | Antihero | Marvel |
| SHIELD | Intelligence agency | Nick Fury | Supporting | Marvel |
| SHIELD (MCU) | Intelligence agency | Nick Fury (MCU) | Supporting | Marvel |
| SWORD | Space agency | Phil Coulson | Supporting | Marvel |
| The Hand | Ninja cult | Elektra | Antihero | Marvel |
| Time Variance Authority | Bureaucratic authority | He Who Remains | Villain | Marvel |
| Wakanda | Nation state | Black Panther | Hero | Marvel |
| Wakanda (MCU) | Nation state | Black Panther (MCU) | Hero | Marvel |
| Weapon X | Black programme | Sabretooth | Villain | Marvel |
| Xavier Institute | School and sanctuary | Professor X | Supporting | Marvel |

## 13. Cross-universe characters (same alias family)

Shows how the comic and screen records are kept apart rather than merged.

```sql
SELECT alias, continuity, character_type, current_status
FROM uni_character
WHERE alias LIKE '%(MCU)%' OR alias LIKE '%(DCEU)%'
ORDER BY alias
```

| alias | continuity | character_type | current_status |
| --- | --- | --- | --- |
| Amanda Waller (DCEU) | DCEU (Earth-1) | Supporting | Active |
| Aquaman (DCEU) | DCEU (Earth-1) | Hero | Active |
| Batman (DCEU) | DCEU (Earth-1) | Hero | Active |
| Black Manta (DCEU) | DCEU (Earth-1) | Villain | Active |
| Black Panther (MCU) | Marvel Cinematic Universe (Earth-199999) | Hero | Active |
| Black Widow (MCU) | Marvel Cinematic Universe (Earth-199999) | Hero | Deceased |
| Captain America (MCU) | Marvel Cinematic Universe (Earth-199999) | Hero | Retired |
| Captain Boomerang (DCEU) | DCEU (Earth-1) | Villain | Deceased |
| Captain Marvel (MCU) | Marvel Cinematic Universe (Earth-199999) | Hero | Active |
| Cyborg (DCEU) | DCEU (Earth-1) | Hero | Active |
| Daredevil (MCU) | Marvel Cinematic Universe (Earth-199999) | Hero | Active |
| Deadshot (DCEU) | DCEU (Earth-1) | Villain | Active |
| Doctor Strange (MCU) | Marvel Cinematic Universe (Earth-199999) | Hero | Active |
| Drax (MCU) | Marvel Cinematic Universe (Earth-199999) | Antihero | Active |
| Falcon (MCU) | Marvel Cinematic Universe (Earth-199999) | Hero | Active |
| Gamora (MCU) | Marvel Cinematic Universe (Earth-199999) | Antihero | Deceased (2018 timeline) |
| General Zod (DCEU) | DCEU (Earth-1) | Villain | Deceased |
| Groot (MCU) | Marvel Cinematic Universe (Earth-199999) | Hero | Active |
| Harley Quinn (DCEU) | DCEU (Earth-1) | Antihero | Active |
| Hawkeye (MCU) | Marvel Cinematic Universe (Earth-199999) | Hero | Active |
| Hela (MCU) | Marvel Cinematic Universe (Earth-199999) | Villain | Deceased |
| Hulk (MCU) | Marvel Cinematic Universe (Earth-199999) | Hero | Active |
| Iron Fist (MCU) | Marvel Cinematic Universe (Earth-199999) | Hero | Active |
| Iron Man (MCU) | Marvel Cinematic Universe (Earth-199999) | Hero | Deceased (2018 snapshot: active) |
| Jessica Jones (MCU) | Marvel Cinematic Universe (Earth-199999) | Antihero | Active |
| Joker (DCEU) | DCEU (Earth-1) | Villain | Active |
| Killer Croc (DCEU) | DCEU (Earth-1) | Villain | Active |
| Loki (MCU) | Marvel Cinematic Universe (Earth-199999) | Antihero | Deceased (2018 timeline) |
| Luke Cage (MCU) | Marvel Cinematic Universe (Earth-199999) | Hero | Active |
| Mantis (MCU) | Marvel Cinematic Universe (Earth-199999) | Hero | Active |
| Mera (DCEU) | DCEU (Earth-1) | Supporting | Active |
| Moon Knight (MCU) | Marvel Cinematic Universe (Earth-199999) | Antihero | Active |
| Nebula (MCU) | Marvel Cinematic Universe (Earth-199999) | Antihero | Active |
| Nick Fury (MCU) | Marvel Cinematic Universe (Earth-199999) | Supporting | Active |
| Ocean Master (DCEU) | DCEU (Earth-1) | Villain | Deposed |
| Red Skull (MCU) | Marvel Cinematic Universe (Earth-199999) | Villain | Deceased (cursed) |
| Rocket (MCU) | Marvel Cinematic Universe (Earth-199999) | Hero | Active |
| Scarlet Witch (MCU) | Marvel Cinematic Universe (Earth-199999) | Hero | Deceased (presumed) |
| Spider-Man (MCU) | Marvel Cinematic Universe (Earth-199999) | Hero | Active |
| Star-Lord (MCU) | Marvel Cinematic Universe (Earth-199999) | Hero | Active |
| Steppenwolf (DCEU) | DCEU (Earth-1) | Villain | Deceased |
| Superman (DCEU) | DCEU (Earth-1) | Hero | Active |
| Thanos (MCU) | Marvel Cinematic Universe (Earth-199999) | Villain | Deceased |
| The Flash (DCEU) | DCEU (Earth-1) | Hero | Active |
| The Scarlet Witch (MCU) | Marvel Cinematic Universe (Earth-199999) | Hero | Active |
| Thor (MCU) | Marvel Cinematic Universe (Earth-199999) | Hero | Active |
| Ultron (MCU) | Marvel Cinematic Universe (Earth-199999) | Villain | Deceased |
| Vision (MCU) | Marvel Cinematic Universe (Earth-199999) | Hero | Deceased |
| War Machine (MCU) | Marvel Cinematic Universe (Earth-199999) | Hero | Active |
| Winter Soldier (MCU) | Marvel Cinematic Universe (Earth-199999) | Antihero | Active |
| Wonder Woman (DCEU) | DCEU (Earth-1) | Hero | Active |

## 14. Every table, one row count

UNION ALL over literal selects: the row-count ledger for the viva.

```sql
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
ORDER BY table_name
```

| table_name | rows |
| --- | --- |
| uni_battle | 80 |
| uni_battle_participation | 417 |
| uni_character | 252 |
| uni_character_power | 1252 |
| uni_comic | 141 |
| uni_content | 100 |
| uni_membership | 208 |
| uni_mission | 60 |
| uni_mission_participation | 264 |
| uni_organization | 51 |
| uni_power | 103 |
| uni_relationship | 188 |
| uni_team | 36 |
| uni_universe | 2 |

## Summary

- Queries defined: 14
- Queries that ran: 14
- Queries that failed: 0

All queries ran against the loaded database. Nothing in this sheet is hand-written output.
