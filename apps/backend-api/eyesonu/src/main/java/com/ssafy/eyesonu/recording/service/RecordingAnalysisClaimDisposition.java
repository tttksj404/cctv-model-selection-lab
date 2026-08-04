package com.ssafy.eyesonu.recording.service;

/** The only states a worker may receive after attempting to claim a job. */
public enum RecordingAnalysisClaimDisposition {
    CLAIMED,
    LEASE_HELD_BY_SELF,
    LEASE_HELD_BY_OTHER,
    RETRY_PENDING,
    TERMINAL
}
