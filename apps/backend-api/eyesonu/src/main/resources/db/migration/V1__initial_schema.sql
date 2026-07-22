CREATE TABLE `admins` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `login_id` VARCHAR(50) NOT NULL,
    `password_hash` VARCHAR(255) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `name` VARCHAR(50) NOT NULL,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (`id`),
    CONSTRAINT `uk_admins_login_id` UNIQUE (`login_id`)
) ENGINE = InnoDB
  DEFAULT CHARACTER SET = utf8mb4
  COLLATE = utf8mb4_0900_ai_ci;

CREATE TABLE `reporters` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `name` VARCHAR(50) NOT NULL,
    `phone` VARCHAR(20) NOT NULL,
    `email` VARCHAR(100) NULL,
    `phone_verified` BOOLEAN NOT NULL DEFAULT FALSE,
    `verified_at` DATETIME(6) NULL,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (`id`),
    CONSTRAINT `ck_reporters_phone_verified` CHECK (`phone_verified` IN (FALSE, TRUE)),
    CONSTRAINT `ck_reporters_verification` CHECK (
        (`phone_verified` = FALSE AND `verified_at` IS NULL)
        OR (`phone_verified` = TRUE AND `verified_at` IS NOT NULL)
    )
) ENGINE = InnoDB
  DEFAULT CHARACTER SET = utf8mb4
  COLLATE = utf8mb4_0900_ai_ci;

CREATE TABLE `cases` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `reporter_id` BIGINT NOT NULL,
    `case_number` VARCHAR(30) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `status` VARCHAR(30) NOT NULL DEFAULT 'RECEIVED',
    `report_content` TEXT NOT NULL,
    `missing_name` VARCHAR(50) NOT NULL,
    `gender` VARCHAR(20) NULL,
    `age_group` VARCHAR(20) NULL,
    `appearance` TEXT NOT NULL,
    `belongings` TEXT NULL,
    `photo_s3_key` VARCHAR(500) COLLATE utf8mb4_bin NULL,
    `last_seen_time` DATETIME(6) NOT NULL,
    `last_seen_lat` DECIMAL(10, 7) NULL,
    `last_seen_lng` DECIMAL(10, 7) NULL,
    `last_seen_address` VARCHAR(255) NULL,
    `reported_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `closed_at` DATETIME(6) NULL,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (`id`),
    CONSTRAINT `uk_cases_case_number` UNIQUE (`case_number`),
    KEY `ix_cases_reporter_id` (`reporter_id`),
    KEY `ix_cases_status_reported_at` (`status`, `reported_at` DESC),
    CONSTRAINT `fk_cases_reporter` FOREIGN KEY (`reporter_id`)
        REFERENCES `reporters` (`id`)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,
    CONSTRAINT `ck_cases_status` CHECK (
        `status` IN ('RECEIVED', 'SEARCHING', 'CANDIDATE_FOUND', 'FIELD_SEARCH', 'CLOSED')
    ),
    CONSTRAINT `ck_cases_last_seen_coordinates` CHECK (
        (`last_seen_lat` IS NULL AND `last_seen_lng` IS NULL)
        OR (`last_seen_lat` IS NOT NULL AND `last_seen_lng` IS NOT NULL)
    ),
    CONSTRAINT `ck_cases_last_seen_lat` CHECK (
        `last_seen_lat` IS NULL
        OR `last_seen_lat` BETWEEN -90.0000000 AND 90.0000000
    ),
    CONSTRAINT `ck_cases_last_seen_lng` CHECK (
        `last_seen_lng` IS NULL
        OR `last_seen_lng` BETWEEN -180.0000000 AND 180.0000000
    ),
    CONSTRAINT `ck_cases_closed` CHECK (
        (`status` = 'CLOSED' AND `closed_at` IS NOT NULL)
        OR (`status` <> 'CLOSED' AND `closed_at` IS NULL)
    )
) ENGINE = InnoDB
  DEFAULT CHARACTER SET = utf8mb4
  COLLATE = utf8mb4_0900_ai_ci;

CREATE TABLE `search_conditions` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `case_id` BIGINT NOT NULL,
    `prompt` TEXT NOT NULL,
    `exclusion_prompt` TEXT NULL,
    `search_start` DATETIME(6) NULL,
    `search_end` DATETIME(6) NULL,
    `search_area` VARCHAR(255) NULL,
    `similarity_threshold` DECIMAL(5, 4) NOT NULL,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (`id`),
    CONSTRAINT `uk_search_conditions_id_case` UNIQUE (`id`, `case_id`),
    KEY `ix_search_conditions_case_created` (`case_id`, `created_at` DESC),
    CONSTRAINT `fk_search_conditions_case` FOREIGN KEY (`case_id`)
        REFERENCES `cases` (`id`)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,
    CONSTRAINT `ck_search_conditions_threshold` CHECK (
        `similarity_threshold` BETWEEN 0.0000 AND 1.0000
    ),
    CONSTRAINT `ck_search_conditions_time_range` CHECK (
        (`search_start` IS NULL AND `search_end` IS NULL)
        OR (
            `search_start` IS NOT NULL
            AND `search_end` IS NOT NULL
            AND `search_end` >= `search_start`
        )
    )
) ENGINE = InnoDB
  DEFAULT CHARACTER SET = utf8mb4
  COLLATE = utf8mb4_0900_ai_ci;

CREATE TABLE `cameras` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `camera_name` VARCHAR(100) NOT NULL,
    `camera_code` VARCHAR(100) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `device_key_hash` VARCHAR(255) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    `latitude` DECIMAL(10, 7) NOT NULL,
    `longitude` DECIMAL(10, 7) NOT NULL,
    `address` VARCHAR(255) NOT NULL,
    `stream_url` VARCHAR(500) COLLATE utf8mb4_bin NOT NULL,
    `status` VARCHAR(20) NOT NULL DEFAULT 'OFFLINE',
    `last_heartbeat` DATETIME(6) NULL,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (`id`),
    CONSTRAINT `uk_cameras_camera_code` UNIQUE (`camera_code`),
    CONSTRAINT `uk_cameras_device_key_hash` UNIQUE (`device_key_hash`),
    KEY `ix_cameras_status_heartbeat` (`status`, `last_heartbeat` DESC),
    KEY `ix_cameras_coordinates` (`latitude`, `longitude`),
    CONSTRAINT `ck_cameras_status` CHECK (`status` IN ('ONLINE', 'OFFLINE', 'ERROR')),
    CONSTRAINT `ck_cameras_latitude` CHECK (
        `latitude` BETWEEN -90.0000000 AND 90.0000000
    ),
    CONSTRAINT `ck_cameras_longitude` CHECK (
        `longitude` BETWEEN -180.0000000 AND 180.0000000
    )
) ENGINE = InnoDB
  DEFAULT CHARACTER SET = utf8mb4
  COLLATE = utf8mb4_0900_ai_ci;

CREATE TABLE `case_cameras` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `case_id` BIGINT NOT NULL,
    `camera_id` BIGINT NOT NULL,
    `search_enabled` BOOLEAN NOT NULL DEFAULT TRUE,
    `selected_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `removed_at` DATETIME(6) NULL,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (`id`),
    CONSTRAINT `uk_case_cameras_case_camera` UNIQUE (`case_id`, `camera_id`),
    KEY `ix_case_cameras_case_enabled_selected` (`case_id`, `search_enabled`, `selected_at` DESC),
    KEY `ix_case_cameras_camera_enabled` (`camera_id`, `search_enabled`),
    CONSTRAINT `fk_case_cameras_case` FOREIGN KEY (`case_id`)
        REFERENCES `cases` (`id`)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,
    CONSTRAINT `fk_case_cameras_camera` FOREIGN KEY (`camera_id`)
        REFERENCES `cameras` (`id`)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,
    CONSTRAINT `ck_case_cameras_search_enabled` CHECK (`search_enabled` IN (FALSE, TRUE)),
    CONSTRAINT `ck_case_cameras_active_state` CHECK (
        (`search_enabled` = TRUE AND `removed_at` IS NULL)
        OR (`search_enabled` = FALSE AND `removed_at` IS NOT NULL)
    ),
    CONSTRAINT `ck_case_cameras_removed_at` CHECK (
        `removed_at` IS NULL OR `removed_at` >= `selected_at`
    )
) ENGINE = InnoDB
  DEFAULT CHARACTER SET = utf8mb4
  COLLATE = utf8mb4_0900_ai_ci;

CREATE TABLE `recordings` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `camera_id` BIGINT NOT NULL,
    `start_time` DATETIME(6) NOT NULL,
    `end_time` DATETIME(6) NOT NULL,
    `s3_key` VARCHAR(500) COLLATE utf8mb4_bin NOT NULL,
    `file_size` BIGINT NULL,
    `upload_status` VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (`id`),
    CONSTRAINT `uk_recordings_s3_key` UNIQUE (`s3_key`),
    KEY `ix_recordings_camera_start_time` (`camera_id`, `start_time` DESC),
    KEY `ix_recordings_upload_created` (`upload_status`, `created_at` DESC),
    CONSTRAINT `fk_recordings_camera` FOREIGN KEY (`camera_id`)
        REFERENCES `cameras` (`id`)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,
    CONSTRAINT `ck_recordings_time_range` CHECK (`end_time` >= `start_time`),
    CONSTRAINT `ck_recordings_file_size` CHECK (`file_size` IS NULL OR `file_size` >= 0),
    CONSTRAINT `ck_recordings_upload_status` CHECK (
        `upload_status` IN ('PENDING', 'UPLOADING', 'COMPLETED', 'FAILED')
    )
) ENGINE = InnoDB
  DEFAULT CHARACTER SET = utf8mb4
  COLLATE = utf8mb4_0900_ai_ci;

CREATE TABLE `candidates` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `case_id` BIGINT NOT NULL,
    `camera_id` BIGINT NOT NULL,
    `detected_time` DATETIME(6) NOT NULL,
    `similarity` DECIMAL(5, 4) NOT NULL,
    `image_s3_key` VARCHAR(500) COLLATE utf8mb4_bin NOT NULL,
    `clip_s3_key` VARCHAR(500) COLLATE utf8mb4_bin NULL,
    `clip_status` VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    `review_status` VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    `review_comment` TEXT NULL,
    `reviewed_by` BIGINT NULL,
    `reviewed_at` DATETIME(6) NULL,
    `version` BIGINT NOT NULL DEFAULT 0,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (`id`),
    CONSTRAINT `uk_candidates_id_case` UNIQUE (`id`, `case_id`),
    KEY `ix_candidates_case_review_detected` (`case_id`, `review_status`, `detected_time` DESC),
    KEY `ix_candidates_case_similarity_detected` (`case_id`, `similarity` DESC, `detected_time` DESC),
    KEY `ix_candidates_camera_detected` (`camera_id`, `detected_time` DESC),
    KEY `ix_candidates_reviewer_reviewed` (`reviewed_by`, `reviewed_at` DESC),
    CONSTRAINT `fk_candidates_case` FOREIGN KEY (`case_id`)
        REFERENCES `cases` (`id`)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,
    CONSTRAINT `fk_candidates_camera` FOREIGN KEY (`camera_id`)
        REFERENCES `cameras` (`id`)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,
    CONSTRAINT `fk_candidates_reviewer` FOREIGN KEY (`reviewed_by`)
        REFERENCES `admins` (`id`)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,
    CONSTRAINT `ck_candidates_similarity` CHECK (`similarity` BETWEEN 0.0000 AND 1.0000),
    CONSTRAINT `ck_candidates_clip_status` CHECK (
        `clip_status` IN ('PENDING', 'PROCESSING', 'READY', 'FAILED')
    ),
    CONSTRAINT `ck_candidates_review_status` CHECK (
        `review_status` IN ('PENDING', 'KEPT', 'CONFIRMED', 'REJECTED')
    ),
    CONSTRAINT `ck_candidates_review` CHECK (
        (`review_status` = 'PENDING' AND `reviewed_by` IS NULL AND `reviewed_at` IS NULL)
        OR (
            `review_status` <> 'PENDING'
            AND `reviewed_by` IS NOT NULL
            AND `reviewed_at` IS NOT NULL
        )
    ),
    CONSTRAINT `ck_candidates_version` CHECK (`version` >= 0)
) ENGINE = InnoDB
  DEFAULT CHARACTER SET = utf8mb4
  COLLATE = utf8mb4_0900_ai_ci;

CREATE TABLE `analysis_jobs` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `case_id` BIGINT NOT NULL,
    `search_condition_id` BIGINT NULL,
    `recording_id` BIGINT NULL,
    `candidate_id` BIGINT NULL,
    `job_type` VARCHAR(30) NOT NULL,
    `status` VARCHAR(20) NOT NULL DEFAULT 'QUEUED',
    `retry_count` INT NOT NULL DEFAULT 0,
    `error_message` TEXT NULL,
    `requested_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `started_at` DATETIME(6) NULL,
    `completed_at` DATETIME(6) NULL,
    PRIMARY KEY (`id`),
    KEY `ix_analysis_jobs_case_status_requested` (`case_id`, `status`, `requested_at` DESC),
    KEY `ix_analysis_jobs_case_type_requested` (`case_id`, `job_type`, `requested_at` DESC),
    KEY `ix_analysis_jobs_search_condition` (`search_condition_id`, `case_id`),
    KEY `ix_analysis_jobs_recording` (`recording_id`),
    KEY `ix_analysis_jobs_candidate` (`candidate_id`, `case_id`),
    CONSTRAINT `fk_analysis_jobs_case` FOREIGN KEY (`case_id`)
        REFERENCES `cases` (`id`)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,
    CONSTRAINT `fk_analysis_jobs_search_condition` FOREIGN KEY (`search_condition_id`, `case_id`)
        REFERENCES `search_conditions` (`id`, `case_id`)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,
    CONSTRAINT `fk_analysis_jobs_recording` FOREIGN KEY (`recording_id`)
        REFERENCES `recordings` (`id`)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,
    CONSTRAINT `fk_analysis_jobs_candidate` FOREIGN KEY (`candidate_id`, `case_id`)
        REFERENCES `candidates` (`id`, `case_id`)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,
    CONSTRAINT `ck_analysis_jobs_type` CHECK (
        `job_type` IN ('RECORDING_ANALYSIS', 'CLIP_GENERATION')
    ),
    CONSTRAINT `ck_analysis_jobs_target` CHECK (
        (
            `job_type` = 'RECORDING_ANALYSIS'
            AND `search_condition_id` IS NOT NULL
            AND `recording_id` IS NOT NULL
            AND `candidate_id` IS NULL
        )
        OR (
            `job_type` = 'CLIP_GENERATION'
            AND `search_condition_id` IS NULL
            AND `recording_id` IS NULL
            AND `candidate_id` IS NOT NULL
        )
    ),
    CONSTRAINT `ck_analysis_jobs_status` CHECK (
        `status` IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED')
    ),
    CONSTRAINT `ck_analysis_jobs_retry_count` CHECK (`retry_count` >= 0),
    CONSTRAINT `ck_analysis_jobs_started_at` CHECK (
        `started_at` IS NULL OR `started_at` >= `requested_at`
    ),
    CONSTRAINT `ck_analysis_jobs_completed_at` CHECK (
        `completed_at` IS NULL
        OR (`started_at` IS NULL AND `completed_at` >= `requested_at`)
        OR (`started_at` IS NOT NULL AND `completed_at` >= `started_at`)
    )
) ENGINE = InnoDB
  DEFAULT CHARACTER SET = utf8mb4
  COLLATE = utf8mb4_0900_ai_ci;

CREATE TABLE `audit_logs` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `admin_id` BIGINT NULL,
    `case_id` BIGINT NULL,
    `action_type` VARCHAR(30) NOT NULL,
    `target_type` VARCHAR(30) NULL,
    `target_id` BIGINT NULL,
    `before_value` JSON NULL,
    `after_value` JSON NULL,
    `detail` TEXT NULL,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (`id`),
    KEY `ix_audit_logs_case_created` (`case_id`, `created_at` DESC),
    KEY `ix_audit_logs_admin_created` (`admin_id`, `created_at` DESC),
    KEY `ix_audit_logs_action_created` (`action_type`, `created_at` DESC),
    KEY `ix_audit_logs_target_created` (`target_type`, `target_id`, `created_at` DESC),
    CONSTRAINT `fk_audit_logs_admin` FOREIGN KEY (`admin_id`)
        REFERENCES `admins` (`id`)
        ON DELETE SET NULL
        ON UPDATE RESTRICT,
    CONSTRAINT `fk_audit_logs_case` FOREIGN KEY (`case_id`)
        REFERENCES `cases` (`id`)
        ON DELETE SET NULL
        ON UPDATE RESTRICT
) ENGINE = InnoDB
  DEFAULT CHARACTER SET = utf8mb4
  COLLATE = utf8mb4_0900_ai_ci;
