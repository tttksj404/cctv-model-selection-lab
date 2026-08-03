package com.ssafy.eyesonu.recording.service;

import com.ssafy.eyesonu.recording.domain.AnalysisJob;

public record RecordingAnalysisJobClaimResult(AnalysisJob job, boolean duplicate) {
}
