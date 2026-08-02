package com.ssafy.eyesonu.recording.service;

import com.ssafy.eyesonu.auth.device.MediaServerPrincipal;
import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.missingcase.dto.device.CandidateEventCreateRequest;
import com.ssafy.eyesonu.missingcase.dto.device.CandidateEventCreateResponse;
import com.ssafy.eyesonu.missingcase.service.CandidateEventCommandService;
import com.ssafy.eyesonu.recording.domain.AnalysisJob;
import com.ssafy.eyesonu.recording.dto.admin.RecordingAnalysisJobResponse;
import com.ssafy.eyesonu.recording.dto.device.RecordingAnalysisJobResultResponse;
import com.ssafy.eyesonu.recording.mapper.AnalysisJobMapper;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class RecordingAnalysisJobResultService {

    private static final String RUNNING = "RUNNING";

    private final AnalysisJobMapper analysisJobMapper;
    private final CandidateEventCommandService candidateEventCommandService;

    public RecordingAnalysisJobResultService(
            AnalysisJobMapper analysisJobMapper,
            CandidateEventCommandService candidateEventCommandService) {
        this.analysisJobMapper = analysisJobMapper;
        this.candidateEventCommandService = candidateEventCommandService;
    }

    @Transactional
    public RecordingAnalysisJobResultResponse complete(
            MediaServerPrincipal principal, Long jobId, CandidateEventCreateRequest request) {
        AnalysisJob job = analysisJobMapper.findRecordingAnalysisById(jobId);
        if (job == null) {
            throw new ApiException(HttpStatus.NOT_FOUND, "RESOURCE_NOT_FOUND",
                    "Recording analysis job was not found.");
        }
        if (!RUNNING.equals(job.getStatus())) {
            throw new ApiException(HttpStatus.CONFLICT, "RESOURCE_STATE_CONFLICT",
                    "Only running recording analysis jobs can submit results.");
        }
        if (!job.getCaseId().equals(request.caseId())) {
            throw new ApiException(HttpStatus.UNPROCESSABLE_ENTITY, "BUSINESS_RULE_VIOLATION",
                    "Candidate result case does not match the analysis job.");
        }

        CandidateEventCreateResponse candidateResult = candidateEventCommandService.create(principal, request);
        if (analysisJobMapper.markSucceeded(job.getCaseId(), jobId) != 1) {
            throw new ApiException(HttpStatus.CONFLICT, "RESOURCE_STATE_CONFLICT",
                    "Recording analysis job was changed before its result was completed.");
        }

        AnalysisJob completed = analysisJobMapper.findRecordingAnalysisById(jobId);
        return new RecordingAnalysisJobResultResponse(
                RecordingAnalysisJobResponse.from(completed), candidateResult);
    }
}
