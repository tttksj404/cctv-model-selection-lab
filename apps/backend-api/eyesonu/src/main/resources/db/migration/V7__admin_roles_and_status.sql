ALTER TABLE `admins`
    ADD COLUMN `role` VARCHAR(20) NOT NULL DEFAULT 'ADMIN' AFTER `name`,
    ADD COLUMN `enabled` BOOLEAN NOT NULL DEFAULT TRUE AFTER `role`;

UPDATE `admins`
SET `role` = 'SUPER_ADMIN'
WHERE `id` = (
    SELECT `first_admin_id`
    FROM (
        SELECT MIN(`id`) AS `first_admin_id`
        FROM `admins`
    ) AS `existing_admins`
);

ALTER TABLE `admins`
    ADD CONSTRAINT `ck_admins_role`
        CHECK (`role` IN ('ADMIN', 'SUPER_ADMIN')),
    ADD CONSTRAINT `ck_admins_enabled`
        CHECK (`enabled` IN (FALSE, TRUE));

CREATE INDEX `ix_admins_role_enabled` ON `admins` (`role`, `enabled`);
