ALTER TABLE recording_analysis_outbox
    ADD COLUMN claim_token VARCHAR(36) NULL AFTER status;
