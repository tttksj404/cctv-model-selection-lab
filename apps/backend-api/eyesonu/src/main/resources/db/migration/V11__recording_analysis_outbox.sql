CREATE TABLE recording_analysis_outbox (
    id BIGINT NOT NULL AUTO_INCREMENT,
    command_id VARCHAR(36) NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    job_id BIGINT NOT NULL,
    case_id BIGINT NOT NULL,
    occurred_at DATETIME(6) NOT NULL,
    status VARCHAR(20) NOT NULL,
    retry_count INT NOT NULL DEFAULT 0,
    next_attempt_at DATETIME(6) NOT NULL,
    last_error VARCHAR(1000) NULL,
    published_at DATETIME(6) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT (UTC_TIMESTAMP(6)),
    PRIMARY KEY (id),
    UNIQUE KEY uk_recording_analysis_outbox_command (command_id),
    KEY idx_recording_analysis_outbox_ready (status, next_attempt_at, id),
    CONSTRAINT fk_recording_analysis_outbox_job
        FOREIGN KEY (job_id) REFERENCES analysis_jobs (id),
    CONSTRAINT fk_recording_analysis_outbox_case
        FOREIGN KEY (case_id) REFERENCES cases (id)
);
