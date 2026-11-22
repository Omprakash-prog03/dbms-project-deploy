-- ============================================================================
-- MARVEL & DC UNIVERSE DATABASE MANAGEMENT SYSTEM (MDU)
-- Engine: MySQL 8.0+ | Storage: InnoDB | Charset: utf8mb4
--
-- 14 normalised tables in the portal's own schema (prefix uni_), plus 7 views.
-- The tables are additive: nothing in the campus schema is renamed, altered or
-- dropped, and this file may be run against an already-populated portal.
--
-- Insert order (parents before children):
--   uni_universe -> uni_character -> uni_team -> uni_power -> uni_content
--   -> uni_comic -> uni_mission -> uni_organization -> uni_battle
--   -> uni_membership -> uni_character_power -> uni_mission_participation
--   -> uni_battle_participation -> uni_relationship
-- ============================================================================

CREATE TABLE IF NOT EXISTS uni_universe (
    universe_id      INT AUTO_INCREMENT PRIMARY KEY,
    universe_name    VARCHAR(40)  NOT NULL,
    publisher        VARCHAR(60)  NOT NULL,
    description      TEXT         NOT NULL,
    continuity_type  VARCHAR(140) NOT NULL,
    CONSTRAINT uk_uni_universe_name UNIQUE (universe_name)
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- CHARACTER: heroes, villains, antiheroes, supporting cast and cosmic entities.
-- alias is unique because the dataset gives legacy titles a holder suffix
-- ("Robin (Tim Drake)") so the same title can belong to two people.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS uni_character (
    character_id     INT AUTO_INCREMENT PRIMARY KEY,
    real_name        VARCHAR(120) NULL,
    alias            VARCHAR(120) NOT NULL,
    universe_id      INT          NOT NULL,
    character_type   VARCHAR(30)  NOT NULL,
    species          VARCHAR(60)  NOT NULL,
    gender           VARCHAR(20)  NOT NULL,
    first_appearance VARCHAR(160) NULL,
    origin           TEXT         NOT NULL,
    current_status   VARCHAR(30)  NOT NULL,
    alignment        VARCHAR(20)  NOT NULL,
    continuity       VARCHAR(60)  NOT NULL,
    record_origin    VARCHAR(30)  NOT NULL DEFAULT 'Canon',
    CONSTRAINT uk_uni_character_alias UNIQUE (alias),
    CONSTRAINT chk_uni_character_type CHECK
        (character_type IN ('Hero','Villain','Antihero','Supporting','Cosmic Entity')),
    CONSTRAINT chk_uni_character_alignment CHECK
        (alignment IN ('Good','Evil','Neutral')),
    CONSTRAINT chk_uni_character_origin CHECK
        (record_origin IN ('Canon','Original addition')),
    CONSTRAINT fk_uni_character_universe FOREIGN KEY (universe_id)
        REFERENCES uni_universe (universe_id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS uni_team (
    team_id       INT AUTO_INCREMENT PRIMARY KEY,
    team_name     VARCHAR(120) NOT NULL,
    universe_id   INT          NOT NULL,
    founding_year INT          NULL,
    headquarters  VARCHAR(160) NULL,
    mission       TEXT         NOT NULL,
    team_status   VARCHAR(20)  NOT NULL,
    continuity    VARCHAR(60)  NOT NULL,
    record_origin VARCHAR(30)  NOT NULL DEFAULT 'Canon',
    CONSTRAINT uk_uni_team_name UNIQUE (team_name),
    CONSTRAINT chk_uni_team_year CHECK (founding_year IS NULL OR founding_year BETWEEN 1930 AND 2100),
    CONSTRAINT fk_uni_team_universe FOREIGN KEY (universe_id)
        REFERENCES uni_universe (universe_id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS uni_membership (
    membership_id     INT AUTO_INCREMENT PRIMARY KEY,
    character_id      INT          NOT NULL,
    team_id           INT          NOT NULL,
    joining_date      DATE         NULL,
    departure_date    DATE         NULL,
    membership_status VARCHAR(20)  NOT NULL,
    role              VARCHAR(60)  NOT NULL,
    CONSTRAINT uk_uni_membership UNIQUE (character_id, team_id, joining_date),
    CONSTRAINT chk_uni_membership_order CHECK
        (departure_date IS NULL OR joining_date IS NULL OR departure_date >= joining_date),
    CONSTRAINT fk_uni_membership_character FOREIGN KEY (character_id)
        REFERENCES uni_character (character_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_uni_membership_team FOREIGN KEY (team_id)
        REFERENCES uni_team (team_id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS uni_power (
    power_id    INT AUTO_INCREMENT PRIMARY KEY,
    power_name  VARCHAR(80)  NOT NULL,
    category    VARCHAR(40)  NOT NULL,
    description TEXT         NOT NULL,
    power_level TINYINT      NOT NULL,
    CONSTRAINT uk_uni_power_name UNIQUE (power_name),
    CONSTRAINT chk_uni_power_level CHECK (power_level BETWEEN 1 AND 10)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS uni_character_power (
    mapping_id        INT AUTO_INCREMENT PRIMARY KEY,
    character_id      INT          NOT NULL,
    power_id          INT          NOT NULL,
    proficiency_level VARCHAR(20)  NOT NULL,
    limitations       TEXT         NULL,
    CONSTRAINT uk_uni_character_power UNIQUE (character_id, power_id),
    CONSTRAINT fk_uni_cp_character FOREIGN KEY (character_id)
        REFERENCES uni_character (character_id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_uni_cp_power FOREIGN KEY (power_id)
        REFERENCES uni_power (power_id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS uni_content (
    content_id         INT AUTO_INCREMENT PRIMARY KEY,
    title              VARCHAR(160) NOT NULL,
    universe_id        INT          NOT NULL,
    release_year       INT          NOT NULL,
    content_type       VARCHAR(30)  NOT NULL,
    director           VARCHAR(120) NULL,
    production_studio  VARCHAR(120) NOT NULL,
    duration_minutes   INT          NULL,
    rating             VARCHAR(20)  NULL,
    synopsis           TEXT         NOT NULL,
    continuity         VARCHAR(60)  NOT NULL,
    CONSTRAINT uk_uni_content UNIQUE (title, release_year, content_type),
    CONSTRAINT chk_uni_content_year CHECK (release_year BETWEEN 1930 AND 2100),
    CONSTRAINT chk_uni_content_type CHECK
        (content_type IN ('Film','Television series','Animated film','Animated series','Television special')),
    CONSTRAINT fk_uni_content_universe FOREIGN KEY (universe_id)
        REFERENCES uni_universe (universe_id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS uni_comic (
    comic_id                INT AUTO_INCREMENT PRIMARY KEY,
    title                   VARCHAR(160) NOT NULL,
    universe_id             INT          NOT NULL,
    issue_number            VARCHAR(20)  NOT NULL,
    publication_year        INT          NOT NULL,
    writer                  VARCHAR(120) NULL,
    artist                  VARCHAR(120) NULL,
    storyline               VARCHAR(120) NULL,
    associated_character_id INT          NULL,
    continuity              VARCHAR(60)  NOT NULL,
    CONSTRAINT uk_uni_comic UNIQUE (title, issue_number, publication_year),
    CONSTRAINT chk_uni_comic_year CHECK (publication_year BETWEEN 1930 AND 2100),
    CONSTRAINT fk_uni_comic_universe FOREIGN KEY (universe_id)
        REFERENCES uni_universe (universe_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_uni_comic_character FOREIGN KEY (associated_character_id)
        REFERENCES uni_character (character_id) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS uni_mission (
    mission_id         INT AUTO_INCREMENT PRIMARY KEY,
    mission_name       VARCHAR(160) NOT NULL,
    universe_id        INT          NOT NULL,
    storyline_category VARCHAR(40)  NOT NULL,
    start_year         INT          NOT NULL,
    end_year           INT          NULL,
    description        TEXT         NOT NULL,
    outcome            VARCHAR(60)  NOT NULL,
    continuity         VARCHAR(60)  NOT NULL,
    CONSTRAINT uk_uni_mission_name UNIQUE (mission_name),
    CONSTRAINT chk_uni_mission_years CHECK
        (end_year IS NULL OR end_year >= start_year),
    CONSTRAINT chk_uni_mission_category CHECK
        (storyline_category IN ('Comic event','Comic arc','Film saga','Television saga','Crossover')),
    CONSTRAINT fk_uni_mission_universe FOREIGN KEY (universe_id)
        REFERENCES uni_universe (universe_id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS uni_mission_participation (
    participation_id INT AUTO_INCREMENT PRIMARY KEY,
    character_id     INT         NOT NULL,
    mission_id       INT         NOT NULL,
    role             VARCHAR(60) NOT NULL,
    outcome          VARCHAR(80) NOT NULL,
    survival_status  VARCHAR(20) NOT NULL,
    CONSTRAINT uk_uni_mission_participation UNIQUE (character_id, mission_id),
    CONSTRAINT chk_uni_mission_survival CHECK
        (survival_status IN ('Survived','Killed','Presumed dead','Unknown')),
    CONSTRAINT fk_uni_mp_character FOREIGN KEY (character_id)
        REFERENCES uni_character (character_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_uni_mp_mission FOREIGN KEY (mission_id)
        REFERENCES uni_mission (mission_id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS uni_organization (
    organization_id     INT AUTO_INCREMENT PRIMARY KEY,
    organization_name   VARCHAR(120) NOT NULL,
    universe_id         INT          NOT NULL,
    organization_type   VARCHAR(40)  NOT NULL,
    headquarters        VARCHAR(160) NULL,
    leader_character_id INT          NULL,
    objectives          TEXT         NOT NULL,
    continuity          VARCHAR(60)  NOT NULL,
    record_origin       VARCHAR(30)  NOT NULL DEFAULT 'Canon',
    CONSTRAINT uk_uni_organization UNIQUE (universe_id, organization_name),
    CONSTRAINT fk_uni_org_universe FOREIGN KEY (universe_id)
        REFERENCES uni_universe (universe_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_uni_org_leader FOREIGN KEY (leader_character_id)
        REFERENCES uni_character (character_id) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS uni_battle (
    battle_id    INT AUTO_INCREMENT PRIMARY KEY,
    battle_name  VARCHAR(160) NOT NULL,
    universe_id  INT          NOT NULL,
    location     VARCHAR(160) NOT NULL,
    year         INT          NOT NULL,
    description  TEXT         NOT NULL,
    winner       VARCHAR(120) NOT NULL,
    casualties   INT          NULL,
    continuity   VARCHAR(60)  NOT NULL,
    CONSTRAINT uk_uni_battle UNIQUE (universe_id, battle_name),
    CONSTRAINT chk_uni_battle_casualties CHECK (casualties IS NULL OR casualties >= 0),
    CONSTRAINT fk_uni_battle_universe FOREIGN KEY (universe_id)
        REFERENCES uni_universe (universe_id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS uni_battle_participation (
    participation_id INT AUTO_INCREMENT PRIMARY KEY,
    battle_id        INT         NOT NULL,
    character_id     INT         NOT NULL,
    side             VARCHAR(60) NOT NULL,
    battle_result    VARCHAR(20) NOT NULL,
    status           VARCHAR(30) NOT NULL,
    CONSTRAINT uk_uni_battle_participation UNIQUE (battle_id, character_id),
    CONSTRAINT chk_uni_bp_result CHECK
        (battle_result IN ('Victorious','Defeated','Stalemate')),
    CONSTRAINT fk_uni_bp_battle FOREIGN KEY (battle_id)
        REFERENCES uni_battle (battle_id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_uni_bp_character FOREIGN KEY (character_id)
        REFERENCES uni_character (character_id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- RELATIONSHIP: undirected pair. The CHECK keeps one row per pair per
-- continuity, so "Batman/Joker" cannot also be stored as "Joker/Batman".
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS uni_relationship (
    relationship_id   INT AUTO_INCREMENT PRIMARY KEY,
    character1_id     INT          NOT NULL,
    character2_id     INT          NOT NULL,
    relationship_type VARCHAR(60)  NOT NULL,
    description       TEXT         NOT NULL,
    continuity        VARCHAR(60)  NOT NULL,
    CONSTRAINT uk_uni_relationship UNIQUE (character1_id, character2_id, continuity),
    CONSTRAINT chk_uni_relationship_order CHECK (character1_id < character2_id),
    CONSTRAINT chk_uni_relationship_distinct CHECK (character1_id <> character2_id),
    CONSTRAINT fk_uni_rel_character1 FOREIGN KEY (character1_id)
        REFERENCES uni_character (character_id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_uni_rel_character2 FOREIGN KEY (character2_id)
        REFERENCES uni_character (character_id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- Indexes: every foreign key gets one, plus the columns the screens filter on.
-- ----------------------------------------------------------------------------
CREATE INDEX ix_uni_character_universe ON uni_character (universe_id, character_type);
CREATE INDEX ix_uni_character_alignment ON uni_character (alignment);
CREATE INDEX ix_uni_team_universe ON uni_team (universe_id);
CREATE INDEX ix_uni_membership_team ON uni_membership (team_id, membership_status);
CREATE INDEX ix_uni_membership_character ON uni_membership (character_id);
CREATE INDEX ix_uni_cp_power ON uni_character_power (power_id);
CREATE INDEX ix_uni_content_universe ON uni_content (universe_id, release_year);
CREATE INDEX ix_uni_comic_character ON uni_comic (associated_character_id);
CREATE INDEX ix_uni_comic_universe ON uni_comic (universe_id, publication_year);
CREATE INDEX ix_uni_mission_universe ON uni_mission (universe_id, start_year);
CREATE INDEX ix_uni_mp_mission ON uni_mission_participation (mission_id);
CREATE INDEX ix_uni_org_leader ON uni_organization (leader_character_id);
CREATE INDEX ix_uni_battle_universe ON uni_battle (universe_id, year);
CREATE INDEX ix_uni_bp_character ON uni_battle_participation (character_id);
CREATE INDEX ix_uni_rel_character2 ON uni_relationship (character2_id);
