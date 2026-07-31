UPDATE analysis_jobs duplicate_job
INNER JOIN analysis_jobs kept_job
    ON kept_job.case_id = duplicate_job.case_id
   AND kept_job.search_condition_id = duplicate_job.search_condition_id
   AND kept_job.recording_id = duplicate_job.recording_id
   AND kept_job.job_type = 'RECORDING_ANALYSIS'
   AND kept_job.status IN ('QUEUED', 'RUNNING')
   AND kept_job.id < duplicate_job.id
SET duplicate_job.status = 'CANCELLED',
    duplicate_job.completed_at = UTC_TIMESTAMP(6),
    duplicate_job.error_message = 'Cancelled during duplicate active recording job cleanup.'
WHERE duplicate_job.job_type = 'RECORDING_ANALYSIS'
  AND duplicate_job.status IN ('QUEUED', 'RUNNING');

ALTER TABLE analysis_jobs
    ADD COLUMN active_recording_dedupe_key VARCHAR(100)
        GENERATED ALWAYS AS (
            CASE
                WHEN status IN ('QUEUED', 'RUNNING')
                    THEN CONCAT(job_type, ':', case_id, ':', search_condition_id, ':', recording_id)
                ELSE NULL
            END
        ) STORED,
    ADD UNIQUE KEY uk_analysis_jobs_active_recording (active_recording_dedupe_key);
