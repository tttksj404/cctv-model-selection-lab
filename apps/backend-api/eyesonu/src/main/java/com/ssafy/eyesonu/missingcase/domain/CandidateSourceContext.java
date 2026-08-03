package com.ssafy.eyesonu.missingcase.domain;

public record CandidateSourceContext(
        CandidateSourceType sourceType,
        Long analysisJobId,
        Long recordingId,
        String dedupeScope) {

    public static CandidateSourceContext realtime(Long caseId, Long cameraId) {
        return new CandidateSourceContext(
                CandidateSourceType.REALTIME,
                null,
                null,
                "realtime:" + caseId + ":" + cameraId);
    }

    public static CandidateSourceContext recordingAnalysis(Long analysisJobId, Long recordingId) {
        return new CandidateSourceContext(
                CandidateSourceType.RECORDING_ANALYSIS,
                analysisJobId,
                recordingId,
                "recording-job:" + analysisJobId);
    }
}
