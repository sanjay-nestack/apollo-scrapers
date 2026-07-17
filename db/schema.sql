-- Apollo scraper — MySQL schema
-- Mirrors the three CSVs the scraper produces, one row per account (email).
-- House style matches the existing `nestack` DB: surrogate id PK, created_at/updated_at,
-- utf8mb4_0900_ai_ci, UNIQUE natural key. `email` is UNIQUE so writes can upsert
-- (INSERT ... ON DUPLICATE KEY UPDATE).

-- ---------------------------------------------------------------------------
-- 1. Search data  (was apollo_search_data.csv)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS apollo_search_data (
  id             INT          NOT NULL AUTO_INCREMENT,
  email          VARCHAR(255) NOT NULL,
  status         VARCHAR(50)  DEFAULT NULL,
  last_execution DATETIME     DEFAULT NULL,
  used_credits   INT          DEFAULT NULL,
  total_credits  INT          DEFAULT NULL,
  renews_on      DATETIME     DEFAULT NULL,
  saved_titles   TEXT,
  saved_counts   TEXT,
  total_saved    INT          DEFAULT NULL,
  netnew_counts  TEXT,
  total_netnew   INT          DEFAULT NULL,
  failed_reason  TEXT,
  created_at     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_search_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------------
-- 2. Credits data  (was apollo_credits_only.csv)
--    6-month rolling window of used credits + provided (plan) credits.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS apollo_credits_data (
  id                    INT          NOT NULL AUTO_INCREMENT,
  email                 VARCHAR(255) NOT NULL,
  status                VARCHAR(50)  DEFAULT NULL,
  last_execution        DATETIME     DEFAULT NULL,
  renewal_date          DATETIME     DEFAULT NULL,
  first_month_credits   INT          DEFAULT NULL,
  second_month_credits  INT          DEFAULT NULL,
  third_month_credits   INT          DEFAULT NULL,
  fourth_month_credits  INT          DEFAULT NULL,
  fifth_month_credits   INT          DEFAULT NULL,
  sixth_month_credits   INT          DEFAULT NULL,
  first_month_provided  INT          DEFAULT NULL,
  second_month_provided INT          DEFAULT NULL,
  third_month_provided  INT          DEFAULT NULL,
  fourth_month_provided INT          DEFAULT NULL,
  fifth_month_provided  INT          DEFAULT NULL,
  sixth_month_provided  INT          DEFAULT NULL,
  created_at            TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at            TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_credits_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------------
-- 3. Upload / list data  (was apollo_upload_data_append.csv)
--    monthly_breakdown holds the per-month upload detail as JSON.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS apollo_upload_data (
  id                INT          NOT NULL AUTO_INCREMENT,
  email             VARCHAR(255) NOT NULL,
  data_count        INT          DEFAULT NULL,
  last_uploaded     DATETIME     DEFAULT NULL,
  status            VARCHAR(50)  DEFAULT NULL,
  last_execution    DATETIME(6)  DEFAULT NULL,
  monthly_breakdown JSON         DEFAULT NULL,
  created_at        TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at        TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_upload_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
