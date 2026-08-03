ALTER TABLE `analysis_jobs`
    ADD COLUMN `claimed_by` VARCHAR(100) NULL AFTER `started_at`,
    ADD COLUMN `claim_expires_at` DATETIME(6) NULL AFTER `claimed_by`,
    ADD KEY `ix_analysis_jobs_claim_lease` (`status`, `claim_expires_at`);

CREATE TABLE `recording_analysis_results` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `job_id` BIGINT NOT NULL,
    `result_id` VARCHAR(255) COLLATE utf8mb4_bin NOT NULL,
    `payload_hash` CHAR(64) COLLATE utf8mb4_bin NOT NULL,
    `candidate_count` INT UNSIGNED NOT NULL,
    `received_at` DATETIME(6) NOT NULL DEFAULT (UTC_TIMESTAMP(6)),
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_recording_analysis_results_job` (`job_id`),
    UNIQUE KEY `uk_recording_analysis_results_result_id` (`result_id`),
    CONSTRAINT `fk_recording_analysis_results_job`
        FOREIGN KEY (`job_id`) REFERENCES `analysis_jobs` (`id`)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT
);

ALTER TABLE `recording_analysis_results`
    DROP INDEX `uk_recording_analysis_results_job`,
    ADD COLUMN `attempt` INT NOT NULL DEFAULT 1 AFTER `job_id`,
    ADD COLUMN `status` VARCHAR(20) NOT NULL DEFAULT 'SUCCEEDED' AFTER `payload_hash`,
    ADD COLUMN `error_code` VARCHAR(100) NULL AFTER `candidate_count`,
    ADD COLUMN `error_message` VARCHAR(1000) NULL AFTER `error_code`,
    ADD UNIQUE KEY `uk_recording_analysis_results_job_attempt` (`job_id`, `attempt`),
    ADD CONSTRAINT `ck_recording_analysis_results_attempt` CHECK (`attempt` > 0),
    ADD CONSTRAINT `ck_recording_analysis_results_status`
        CHECK (`status` IN ('SUCCEEDED', 'FAILED')),
    ADD CONSTRAINT `ck_recording_analysis_results_content` CHECK (
        (`status` = 'SUCCEEDED' AND `error_code` IS NULL AND `error_message` IS NULL)
        OR
        (`status` = 'FAILED' AND `candidate_count` = 0 AND `error_code` IS NOT NULL)
    );
