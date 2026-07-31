-- A realtime frame may contain multiple detections. Keep the received event
-- separate from the reviewable, track-level candidate aggregate.

ALTER TABLE `candidates`
    RENAME COLUMN `image_s3_key` TO `crop_object_key`;

ALTER TABLE `candidates`
    ADD COLUMN `frame_object_key` VARCHAR(500) COLLATE utf8mb4_bin NULL AFTER `crop_object_key`,
    ADD COLUMN `track_id` VARCHAR(100) COLLATE utf8mb4_bin NULL AFTER `camera_id`,
    ADD COLUMN `first_detected_at` DATETIME(6) NULL AFTER `detected_time`,
    ADD COLUMN `last_detected_at` DATETIME(6) NULL AFTER `first_detected_at`,
    ADD COLUMN `best_similarity` DECIMAL(5, 4) NULL AFTER `similarity`,
    ADD COLUMN `average_similarity` DECIMAL(5, 4) NULL AFTER `best_similarity`,
    ADD COLUMN `detection_count` INT UNSIGNED NOT NULL DEFAULT 1 AFTER `average_similarity`,
    ADD COLUMN `bounding_box` JSON NULL AFTER `average_similarity`;

UPDATE `candidates`
SET `first_detected_at` = `detected_time`,
    `last_detected_at` = `detected_time`,
    `best_similarity` = `similarity`,
    `average_similarity` = `similarity`
WHERE `first_detected_at` IS NULL;

ALTER TABLE `candidates`
    MODIFY COLUMN `first_detected_at` DATETIME(6) NOT NULL,
    MODIFY COLUMN `last_detected_at` DATETIME(6) NOT NULL,
    MODIFY COLUMN `best_similarity` DECIMAL(5, 4) NOT NULL,
    MODIFY COLUMN `average_similarity` DECIMAL(5, 4) NOT NULL,
    ADD UNIQUE KEY `uk_candidates_case_camera_track`
        (`case_id`, `camera_id`, `track_id`),
    ADD KEY `ix_candidates_case_camera_track_last_detected`
        (`case_id`, `camera_id`, `track_id`, `last_detected_at` DESC),
    ADD CONSTRAINT `ck_candidates_best_similarity`
        CHECK (`best_similarity` BETWEEN 0.0000 AND 1.0000),
    ADD CONSTRAINT `ck_candidates_average_similarity`
        CHECK (`average_similarity` BETWEEN 0.0000 AND 1.0000),
    ADD CONSTRAINT `ck_candidates_detection_count`
        CHECK (`detection_count` > 0);

CREATE TABLE `candidate_events` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `event_id` VARCHAR(255) COLLATE utf8mb4_bin NOT NULL,
    `case_id` BIGINT NOT NULL,
    `camera_id` BIGINT NOT NULL,
    `detected_at` DATETIME(6) NOT NULL,
    `frame_object_key` VARCHAR(500) COLLATE utf8mb4_bin NOT NULL,
    `received_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_candidate_events_event_id` (`event_id`),
    KEY `ix_candidate_events_case_detected` (`case_id`, `detected_at` DESC),
    KEY `ix_candidate_events_camera_detected` (`camera_id`, `detected_at` DESC),
    CONSTRAINT `fk_candidate_events_case` FOREIGN KEY (`case_id`)
        REFERENCES `cases` (`id`)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,
    CONSTRAINT `fk_candidate_events_camera` FOREIGN KEY (`camera_id`)
        REFERENCES `cameras` (`id`)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT
) ENGINE = InnoDB
  DEFAULT CHARACTER SET = utf8mb4
  COLLATE = utf8mb4_0900_ai_ci;

CREATE TABLE `candidate_event_detections` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `candidate_event_id` BIGINT NOT NULL,
    `candidate_id` BIGINT NULL,
    `detection_index` INT UNSIGNED NOT NULL,
    `track_id` VARCHAR(100) COLLATE utf8mb4_bin NOT NULL,
    `crop_object_key` VARCHAR(500) COLLATE utf8mb4_bin NOT NULL,
    `similarity` DECIMAL(5, 4) NOT NULL,
    `bounding_box` JSON NOT NULL,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_candidate_event_detections_index`
        (`candidate_event_id`, `detection_index`),
    KEY `ix_candidate_event_detections_candidate_track`
        (`candidate_id`, `track_id`),
    CONSTRAINT `fk_candidate_event_detections_event` FOREIGN KEY (`candidate_event_id`)
        REFERENCES `candidate_events` (`id`)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,
    CONSTRAINT `fk_candidate_event_detections_candidate` FOREIGN KEY (`candidate_id`)
        REFERENCES `candidates` (`id`)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,
    CONSTRAINT `ck_candidate_event_detections_similarity`
        CHECK (`similarity` BETWEEN 0.0000 AND 1.0000),
    CONSTRAINT `ck_candidate_event_detections_bounding_box`
        CHECK (JSON_TYPE(`bounding_box`) = 'OBJECT')
) ENGINE = InnoDB
  DEFAULT CHARACTER SET = utf8mb4
  COLLATE = utf8mb4_0900_ai_ci;
