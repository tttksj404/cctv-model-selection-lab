ALTER TABLE `reporters`
    DROP CHECK `ck_reporters_verification`,
    DROP CHECK `ck_reporters_phone_verified`,
    DROP COLUMN `phone_verified`,
    DROP COLUMN `verified_at`,
    ADD COLUMN `relation` VARCHAR(50) NULL AFTER `email`;

ALTER TABLE `cases`
    ADD COLUMN `birth_year` SMALLINT NULL AFTER `gender`,
    ADD COLUMN `hair` VARCHAR(255) NULL AFTER `birth_year`,
    ADD COLUMN `face` VARCHAR(255) NULL AFTER `hair`,
    ADD COLUMN `upper_clothing` VARCHAR(255) NULL AFTER `face`,
    ADD COLUMN `lower_clothing` VARCHAR(255) NULL AFTER `upper_clothing`,
    ADD COLUMN `shoes` VARCHAR(255) NULL AFTER `lower_clothing`,
    ADD COLUMN `body_type` VARCHAR(255) NULL AFTER `belongings`,
    ADD COLUMN `distinctive_features` TEXT NULL AFTER `body_type`;

UPDATE `cases`
SET `distinctive_features` = CASE
    WHEN CHAR_LENGTH(TRIM(`appearance`)) > 0 THEN `appearance`
    ELSE '미상'
END
WHERE `distinctive_features` IS NULL;

UPDATE `cases`
SET `gender` = 'UNKNOWN'
WHERE `gender` IS NULL
   OR `gender` NOT IN ('MALE', 'FEMALE', 'UNKNOWN');

UPDATE `cases`
SET `last_seen_address` = '미상'
WHERE `last_seen_address` IS NULL
   OR CHAR_LENGTH(TRIM(`last_seen_address`)) = 0;

ALTER TABLE `cases`
    DROP COLUMN `age_group`,
    DROP COLUMN `appearance`,
    MODIFY COLUMN `gender` VARCHAR(20) NOT NULL,
    MODIFY COLUMN `last_seen_address` VARCHAR(255) NOT NULL,
    ADD CONSTRAINT `uk_cases_reporter_id` UNIQUE (`reporter_id`),
    ADD CONSTRAINT `ck_cases_gender` CHECK (
        `gender` IN ('MALE', 'FEMALE', 'UNKNOWN')
    ),
    ADD CONSTRAINT `ck_cases_birth_year` CHECK (
        `birth_year` IS NULL OR `birth_year` BETWEEN 1900 AND 2100
    ),
    ADD CONSTRAINT `ck_cases_required_text` CHECK (
        CHAR_LENGTH(TRIM(`report_content`)) > 0
        AND CHAR_LENGTH(TRIM(`missing_name`)) > 0
        AND CHAR_LENGTH(TRIM(`last_seen_address`)) > 0
    ),
    ADD CONSTRAINT `ck_cases_appearance_present` CHECK (
        COALESCE(CHAR_LENGTH(TRIM(`hair`)), 0) > 0
        OR COALESCE(CHAR_LENGTH(TRIM(`face`)), 0) > 0
        OR COALESCE(CHAR_LENGTH(TRIM(`upper_clothing`)), 0) > 0
        OR COALESCE(CHAR_LENGTH(TRIM(`lower_clothing`)), 0) > 0
        OR COALESCE(CHAR_LENGTH(TRIM(`shoes`)), 0) > 0
        OR COALESCE(CHAR_LENGTH(TRIM(`belongings`)), 0) > 0
        OR COALESCE(CHAR_LENGTH(TRIM(`body_type`)), 0) > 0
        OR COALESCE(CHAR_LENGTH(TRIM(`distinctive_features`)), 0) > 0
    );
