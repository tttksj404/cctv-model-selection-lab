-- Distinguish realtime candidates from recording-analysis candidates and make
-- track deduplication explicit per source scope.

ALTER TABLE `candidate_events`
    ADD COLUMN `source_type` VARCHAR(30) NOT NULL DEFAULT 'REALTIME' AFTER `camera_id`,
    ADD COLUMN `analysis_job_id` BIGINT NULL AFTER `source_type`,
    ADD COLUMN `recording_id` BIGINT NULL AFTER `analysis_job_id`;

ALTER TABLE `candidates`
    ADD COLUMN `source_type` VARCHAR(30) NOT NULL DEFAULT 'REALTIME' AFTER `camera_id`,
    ADD COLUMN `analysis_job_id` BIGINT NULL AFTER `source_type`,
    ADD COLUMN `recording_id` BIGINT NULL AFTER `analysis_job_id`,
    ADD COLUMN `dedupe_scope` VARCHAR(255) COLLATE utf8mb4_bin NULL AFTER `recording_id`;

-- Candidate rows created before source tracking were realtime submissions.
UPDATE `candidates`
SET `dedupe_scope` = CONCAT('realtime:', `case_id`, ':', `camera_id`)
WHERE `dedupe_scope` IS NULL;

ALTER TABLE `candidates`
    MODIFY COLUMN `dedupe_scope` VARCHAR(255) COLLATE utf8mb4_bin NOT NULL,
    DROP INDEX `uk_candidates_case_camera_track`,
    ADD UNIQUE KEY `uk_candidates_dedupe_scope_track` (`dedupe_scope`, `track_id`),
    ADD KEY `ix_candidates_source_last_detected` (`source_type`, `last_detected_at` DESC),
    ADD KEY `ix_candidates_analysis_job` (`analysis_job_id`),
    ADD KEY `ix_candidates_recording` (`recording_id`),
    ADD CONSTRAINT `fk_candidates_analysis_job` FOREIGN KEY (`analysis_job_id`)
        REFERENCES `analysis_jobs` (`id`)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,
    ADD CONSTRAINT `fk_candidates_recording` FOREIGN KEY (`recording_id`)
        REFERENCES `recordings` (`id`)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,
    ADD CONSTRAINT `ck_candidates_source_type`
        CHECK (`source_type` IN ('REALTIME', 'RECORDING_ANALYSIS')),
    ADD CONSTRAINT `ck_candidates_source_target` CHECK (
        (`source_type` = 'REALTIME' AND `analysis_job_id` IS NULL AND `recording_id` IS NULL)
        OR
        (`source_type` = 'RECORDING_ANALYSIS' AND `analysis_job_id` IS NOT NULL AND `recording_id` IS NOT NULL)
    );

ALTER TABLE `candidate_events`
    ADD KEY `ix_candidate_events_source_detected` (`source_type`, `detected_at` DESC),
    ADD KEY `ix_candidate_events_analysis_job` (`analysis_job_id`),
    ADD KEY `ix_candidate_events_recording` (`recording_id`),
    ADD CONSTRAINT `fk_candidate_events_analysis_job` FOREIGN KEY (`analysis_job_id`)
        REFERENCES `analysis_jobs` (`id`)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,
    ADD CONSTRAINT `fk_candidate_events_recording` FOREIGN KEY (`recording_id`)
        REFERENCES `recordings` (`id`)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,
    ADD CONSTRAINT `ck_candidate_events_source_type`
        CHECK (`source_type` IN ('REALTIME', 'RECORDING_ANALYSIS')),
    ADD CONSTRAINT `ck_candidate_events_source_target` CHECK (
        (`source_type` = 'REALTIME' AND `analysis_job_id` IS NULL AND `recording_id` IS NULL)
        OR
        (`source_type` = 'RECORDING_ANALYSIS' AND `analysis_job_id` IS NOT NULL AND `recording_id` IS NOT NULL)
    );
