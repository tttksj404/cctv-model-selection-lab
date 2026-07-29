DELETE FROM `analysis_jobs`
WHERE `recording_id` IS NOT NULL;

DELETE FROM `recordings`;

ALTER TABLE `recordings`
    DROP INDEX `ix_recordings_camera_start_time`,
    DROP INDEX `ix_recordings_upload_created`,
    DROP CHECK `ck_recordings_time_range`,
    DROP CHECK `ck_recordings_file_size`,
    DROP CHECK `ck_recordings_upload_status`,
    DROP COLUMN `upload_status`,
    MODIFY COLUMN `file_size` BIGINT NOT NULL,
    ADD CONSTRAINT `ck_recordings_time_range` CHECK (`end_time` > `start_time`),
    ADD CONSTRAINT `ck_recordings_file_size` CHECK (`file_size` > 0),
    ADD KEY `ix_recordings_camera_start_id`
        (`camera_id`, `start_time` DESC, `id` DESC),
    ADD KEY `ix_recordings_start_id`
        (`start_time` DESC, `id` DESC),
    ADD KEY `ix_recordings_camera_end_id`
        (`camera_id`, `end_time`, `id` DESC),
    ADD KEY `ix_recordings_end_id`
        (`end_time`, `id` DESC),
    ADD KEY `ix_recordings_camera_created_id`
        (`camera_id`, `created_at` DESC, `id` DESC),
    ADD KEY `ix_recordings_created_id`
        (`created_at` DESC, `id` DESC);

CREATE TABLE `recording_registration_requests` (
    `media_server_id` BIGINT NOT NULL,
    `idempotency_key` CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `request_fingerprint` CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `recording_id` BIGINT NOT NULL,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (`media_server_id`, `idempotency_key`),
    CONSTRAINT `uk_recording_registration_requests_recording` UNIQUE (`recording_id`),
    CONSTRAINT `fk_recording_registration_requests_media_server`
        FOREIGN KEY (`media_server_id`)
        REFERENCES `media_servers` (`id`)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,
    CONSTRAINT `fk_recording_registration_requests_recording`
        FOREIGN KEY (`recording_id`)
        REFERENCES `recordings` (`id`)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT
) ENGINE = InnoDB
  DEFAULT CHARACTER SET = utf8mb4
  COLLATE = utf8mb4_0900_ai_ci;
