ALTER TABLE `analysis_jobs`
    ADD COLUMN `lease_token_hash` CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NULL
        AFTER `claim_expires_at`,
    ADD COLUMN `result_model_key` VARCHAR(100) NULL AFTER `lease_token_hash`,
    ADD COLUMN `result_payload` MEDIUMTEXT NULL AFTER `result_model_key`,
    ADD COLUMN `result_digest` CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NULL
        AFTER `result_payload`,
    ADD KEY `ix_analysis_jobs_worker_result` (`status`, `completed_at` DESC);
