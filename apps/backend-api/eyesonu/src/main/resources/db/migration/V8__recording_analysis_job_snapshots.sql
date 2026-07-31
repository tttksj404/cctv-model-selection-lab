ALTER TABLE analysis_jobs
    ADD COLUMN prompt_snapshot TEXT NULL AFTER recording_id,
    ADD COLUMN exclusion_prompt_snapshot TEXT NULL AFTER prompt_snapshot,
    ADD COLUMN search_start_snapshot DATETIME(6) NULL AFTER exclusion_prompt_snapshot,
    ADD COLUMN search_end_snapshot DATETIME(6) NULL AFTER search_start_snapshot,
    ADD COLUMN search_area_snapshot VARCHAR(255) NULL AFTER search_end_snapshot,
    ADD COLUMN similarity_threshold_snapshot DECIMAL(5, 4) NULL AFTER search_area_snapshot;
