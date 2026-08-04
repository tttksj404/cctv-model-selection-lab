ALTER TABLE `analysis_jobs`
    ADD COLUMN `lease_token_hash` CHAR(64) COLLATE utf8mb4_bin NULL AFTER `claim_expires_at`;
