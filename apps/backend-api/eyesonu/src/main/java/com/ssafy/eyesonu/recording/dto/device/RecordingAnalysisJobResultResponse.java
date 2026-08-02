package com.ssafy.eyesonu.recording.dto.device;

import com.ssafy.eyesonu.missingcase.dto.device.CandidateEventCreateResponse;
import com.ssafy.eyesonu.recording.dto.admin.RecordingAnalysisJobResponse;

public record RecordingAnalysisJobResultResponse(
        RecordingAnalysisJobResponse job,
        CandidateEventCreateResponse candidateResult) {
}
