-- LOCAL DEVELOPMENT RECOVERY ONLY.
-- Run with the MySQL command-line client against the `eyesonu` schema after a
-- non-web migration process has applied official V6 and administrator V7.
-- Do not expose or start the normal application until this script succeeds.

DELIMITER $$

DROP PROCEDURE IF EXISTS `reconcile_local_admin_v6_after_flyway`$$

CREATE PROCEDURE `reconcile_local_admin_v6_after_flyway`()
BEGIN
    DECLARE `official_v6_count` INT DEFAULT 0;
    DECLARE `administrator_v7_count` INT DEFAULT 0;
    DECLARE `admin_column_count` INT DEFAULT 0;
    DECLARE `admin_constraint_count` INT DEFAULT 0;
    DECLARE `admin_index_count` INT DEFAULT 0;
    DECLARE `orphan_backup_count` INT DEFAULT 0;
    DECLARE `restoration_mismatch_count` INT DEFAULT 0;
    DECLARE `admin_count` INT DEFAULT 0;
    DECLARE `active_super_admin_count` INT DEFAULT 0;

    IF COALESCE(DATABASE(), '') <> 'eyesonu' THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Recovery must run only against the eyesonu schema';
    END IF;

    SELECT COUNT(*)
    INTO `official_v6_count`
    FROM `flyway_schema_history`
    WHERE `version` = '6'
      AND `script` = 'V6__realtime_candidate_event_model.sql'
      AND `success` = TRUE;

    SELECT COUNT(*)
    INTO `administrator_v7_count`
    FROM `flyway_schema_history`
    WHERE `version` = '7'
      AND `script` = 'V7__admin_roles_and_status.sql'
      AND `success` = TRUE;

    IF `official_v6_count` <> 1 OR `administrator_v7_count` <> 1 THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Expected official V6 and administrator V7 Flyway history';
    END IF;

    SELECT COUNT(*)
    INTO `admin_column_count`
    FROM `information_schema`.`columns`
    WHERE `table_schema` = DATABASE()
      AND `table_name` = 'admins'
      AND `column_name` IN ('role', 'enabled');

    IF `admin_column_count` <> 2 THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Administrator V7 columns are missing';
    END IF;

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

    IF `admin_constraint_count` <> 2 OR `admin_index_count` <> 1 THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Administrator V7 constraints or index are missing';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM `information_schema`.`tables`
        WHERE `table_schema` = DATABASE()
          AND `table_name` = '_local_admin_v6_role_status_backup'
    ) THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Administrator role/status recovery backup is missing';
    END IF;

    SELECT COUNT(*)
    INTO `orphan_backup_count`
    FROM `_local_admin_v6_role_status_backup` AS `backup`
    LEFT JOIN `admins` AS `admin` ON `admin`.`id` = `backup`.`admin_id`
    WHERE `admin`.`id` IS NULL;

    IF `orphan_backup_count` <> 0 THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'A preserved administrator row is missing after migration';
    END IF;

    UPDATE `admins` AS `admin`
    INNER JOIN `_local_admin_v6_role_status_backup` AS `backup`
        ON `backup`.`admin_id` = `admin`.`id`
    SET `admin`.`role` = `backup`.`role`,
        `admin`.`enabled` = `backup`.`enabled`;

    SELECT COUNT(*)
    INTO `restoration_mismatch_count`
    FROM `_local_admin_v6_role_status_backup` AS `backup`
    INNER JOIN `admins` AS `admin` ON `admin`.`id` = `backup`.`admin_id`
    WHERE `admin`.`role` <> `backup`.`role`
       OR `admin`.`enabled` <> `backup`.`enabled`;

    IF `restoration_mismatch_count` <> 0 THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Administrator role/status restoration mismatch';
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
            SET MESSAGE_TEXT = 'No active SUPER_ADMIN remains after data restoration';
    END IF;

    DROP TABLE `_local_admin_v6_role_status_backup`;
END$$

CALL `reconcile_local_admin_v6_after_flyway`()$$
DROP PROCEDURE `reconcile_local_admin_v6_after_flyway`$$

DELIMITER ;

SELECT `version`, `script`, `success`
FROM `flyway_schema_history`
WHERE `version` IN ('6', '7')
ORDER BY `installed_rank`;
