ALTER TABLE analysis_jobs
    ADD COLUMN active_recording_dedupe_key VARCHAR(100)
        GENERATED ALWAYS AS (
            CASE
                WHEN status IN ('QUEUED', 'RUNNING')
                    THEN CONCAT(case_id, ':', search_condition_id, ':', recording_id)
                ELSE NULL
            END
        ) STORED,
    ADD UNIQUE KEY uk_analysis_jobs_active_recording (active_recording_dedupe_key);
