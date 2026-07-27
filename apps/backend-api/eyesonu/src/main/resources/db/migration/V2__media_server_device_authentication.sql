CREATE TABLE `media_servers` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `server_code` VARCHAR(50) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `name` VARCHAR(100) NOT NULL,
    `device_key_id` CHAR(16) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `device_key_hash` VARCHAR(255) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `status` VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (`id`),
    CONSTRAINT `uk_media_servers_server_code` UNIQUE (`server_code`),
    CONSTRAINT `uk_media_servers_device_key_id` UNIQUE (`device_key_id`),
    CONSTRAINT `ck_media_servers_status` CHECK (`status` IN ('ACTIVE', 'DISABLED'))
) ENGINE = InnoDB
  DEFAULT CHARACTER SET = utf8mb4
  COLLATE = utf8mb4_0900_ai_ci;

ALTER TABLE `cameras`
    DROP INDEX `uk_cameras_device_key_hash`,
    DROP COLUMN `device_key_hash`,
    ADD COLUMN `media_server_id` BIGINT NOT NULL AFTER `id`,
    ADD KEY `ix_cameras_media_server_id` (`media_server_id`),
    ADD CONSTRAINT `fk_cameras_media_server` FOREIGN KEY (`media_server_id`)
        REFERENCES `media_servers` (`id`)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT;
