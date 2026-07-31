-- LOCAL DEVELOPMENT RECOVERY ONLY.
-- Run with the MySQL command-line client against the `eyesonu` schema after
-- taking an external mysqldump. The application must remain stopped and
-- unreachable for the entire before -> Flyway -> after recovery sequence.

DELIMITER $$

DROP PROCEDURE IF EXISTS `reconcile_local_admin_v6_before_flyway`$$

CREATE PROCEDURE `reconcile_local_admin_v6_before_flyway`()
BEGIN
    DECLARE `old_v6_count` INT DEFAULT 0;
    DECLARE `later_migration_count` INT DEFAULT 0;
    DECLARE `old_v6_rank` INT DEFAULT 0;
    DECLARE `admin_column_count` INT DEFAULT 0;
    DECLARE `admin_constraint_count` INT DEFAULT 0;
    DECLARE `admin_index_count` INT DEFAULT 0;
    DECLARE `candidate_event_table_count` INT DEFAULT 0;
    DECLARE `legacy_candidate_column_count` INT DEFAULT 0;
    DECLARE `new_candidate_column_count` INT DEFAULT 0;
    DECLARE `admin_count` INT DEFAULT 0;
    DECLARE `active_super_admin_count` INT DEFAULT 0;
    DECLARE `removed_history_count` INT DEFAULT 0;

    IF COALESCE(DATABASE(), '') <> 'eyesonu' THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Recovery must run only against the eyesonu schema';
    END IF;

    SELECT COUNT(*), COALESCE(MAX(`installed_rank`), 0)
    INTO `old_v6_count`, `old_v6_rank`
    FROM `flyway_schema_history`
    WHERE `version` = '6'
      AND `script` = 'V6__admin_roles_and_status.sql'
      AND `success` = TRUE;

    IF `old_v6_count` <> 1 THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Expected exactly one applied local administrator V6';
    END IF;

    SELECT COUNT(*)
    INTO `later_migration_count`
    FROM `flyway_schema_history`
    WHERE `installed_rank` > `old_v6_rank`;

    IF `later_migration_count` <> 0 THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Later Flyway migrations already exist; stop recovery';
    END IF;

    SELECT COUNT(*)
    INTO `admin_column_count`
    FROM `information_schema`.`columns`
    WHERE `table_schema` = DATABASE()
      AND `table_name` = 'admins'
      AND `column_name` IN ('role', 'enabled');

    SELECT COUNT(*)
    INTO `admin_constraint_count`
    FROM `information_schema`.`table_constraints`
    WHERE `table_schema` = DATABASE()
      AND `table_name` = 'admins'
      AND `constraint_name` IN ('ck_admins_role', 'ck_admins_enabled');

    SELECT COUNT(DISTINCT `index_name`)
    INTO `admin_index_count`
    FROM `information_schema`.`statistics`
    WHERE `table_schema` = DATABASE()
      AND `table_name` = 'admins'
      AND `index_name` = 'ix_admins_role_enabled';

    IF `admin_column_count` <> 2
            OR `admin_constraint_count` <> 2
            OR `admin_index_count` <> 1 THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Administrator V6 schema does not match the expected shape';
    END IF;

    SELECT COUNT(*)
    INTO `candidate_event_table_count`
    FROM `information_schema`.`tables`
    WHERE `table_schema` = DATABASE()
      AND `table_name` IN ('candidate_events', 'candidate_event_detections');

    SELECT COUNT(*)
    INTO `legacy_candidate_column_count`
    FROM `information_schema`.`columns`
    WHERE `table_schema` = DATABASE()
      AND `table_name` = 'candidates'
      AND `column_name` = 'image_s3_key';

    SELECT COUNT(*)
    INTO `new_candidate_column_count`
    FROM `information_schema`.`columns`
    WHERE `table_schema` = DATABASE()
      AND `table_name` = 'candidates'
      AND `column_name` = 'crop_object_key';

    IF `candidate_event_table_count` <> 0
            OR `legacy_candidate_column_count` <> 1
            OR `new_candidate_column_count` <> 0 THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Official candidate-event V6 is already present or partially applied';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM `information_schema`.`tables`
        WHERE `table_schema` = DATABASE()
          AND `table_name` = '_local_admin_v6_role_status_backup'
    ) THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Administrator role/status recovery backup already exists';
    END IF;

    SELECT COUNT(*)
    INTO `admin_count`
    FROM `admins`;

    SELECT COUNT(*)
    INTO `active_super_admin_count`
    FROM `admins`
    WHERE `role` = 'SUPER_ADMIN'
      AND `enabled` = TRUE;

    IF `admin_count` > 0 AND `active_super_admin_count` = 0 THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'No active SUPER_ADMIN exists; stop recovery';
    END IF;

    CREATE TABLE `_local_admin_v6_role_status_backup` (
        `admin_id` BIGINT NOT NULL,
        `role` VARCHAR(20) NOT NULL,
        `enabled` BOOLEAN NOT NULL,
        `backed_up_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
        PRIMARY KEY (`admin_id`)
    ) ENGINE = InnoDB
      DEFAULT CHARACTER SET = utf8mb4
      COLLATE = utf8mb4_0900_ai_ci;

    INSERT INTO `_local_admin_v6_role_status_backup` (`admin_id`, `role`, `enabled`)
    SELECT `id`, `role`, `enabled`
    FROM `admins`;

    IF (SELECT COUNT(*) FROM `_local_admin_v6_role_status_backup`) <> `admin_count` THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Administrator role/status backup row count mismatch';
    END IF;

    ALTER TABLE `admins`
        DROP CHECK `ck_admins_role`,
        DROP CHECK `ck_admins_enabled`,
        DROP INDEX `ix_admins_role_enabled`,
        DROP COLUMN `enabled`,
        DROP COLUMN `role`;

    DELETE FROM `flyway_schema_history`
    WHERE `version` = '6'
      AND `script` = 'V6__admin_roles_and_status.sql'
      AND `success` = TRUE;

    SET `removed_history_count` = ROW_COUNT();
    IF `removed_history_count` <> 1 THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Failed to remove exactly one local administrator V6 history row';
    END IF;
END$$

CALL `reconcile_local_admin_v6_before_flyway`()$$
DROP PROCEDURE `reconcile_local_admin_v6_before_flyway`$$

DELIMITER ;

SELECT COUNT(*) AS `preserved_admin_rows`
FROM `_local_admin_v6_role_status_backup`;
