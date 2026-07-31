package com.ssafy.eyesonu.recording.service;

import com.ssafy.eyesonu.audit.service.AuditService;
import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.missingcase.domain.CaseStatus;
import com.ssafy.eyesonu.missingcase.domain.MissingCaseRow;
import com.ssafy.eyesonu.missingcase.domain.SearchConditionRow;
import com.ssafy.eyesonu.missingcase.mapper.MissingCaseMapper;
import com.ssafy.eyesonu.missingcase.service.CaseQueryService;
import com.ssafy.eyesonu.recording.domain.AnalysisJob;
import com.ssafy.eyesonu.recording.domain.Recording;
import com.ssafy.eyesonu.recording.dto.admin.RecordingAnalysisJobCreateRequest;
import com.ssafy.eyesonu.recording.dto.admin.RecordingAnalysisJobResponse;
import com.ssafy.eyesonu.recording.mapper.AnalysisJobMapper;
import com.ssafy.eyesonu.recording.mapper.RecordingMapper;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class RecordingAnalysisJobService {

    private static final String RECORDING_ANALYSIS = "RECORDING_ANALYSIS";
    private static final String QUEUED = "QUEUED";

    private final AnalysisJobMapper analysisJobMapper;
    private final MissingCaseMapper missingCaseMapper;
    private final CaseQueryService caseQueryService;
    private final RecordingMapper recordingMapper;
    private final AuditService auditService;

    public RecordingAnalysisJobService(
            AnalysisJobMapper analysisJobMapper,
            MissingCaseMapper missingCaseMapper,
            CaseQueryService caseQueryService,
            RecordingMapper recordingMapper,
            AuditService auditService) {
        this.analysisJobMapper = analysisJobMapper;
        this.missingCaseMapper = missingCaseMapper;
        this.caseQueryService = caseQueryService;
        this.recordingMapper = recordingMapper;
        this.auditService = auditService;
    }

    @Transactional
    public RecordingAnalysisJobResponse create(
            Long caseId, RecordingAnalysisJobCreateRequest request, Long adminId) {
        MissingCaseRow missingCase = caseQueryService.require(caseId);
        if (missingCase.getStatus() == CaseStatus.CLOSED) {
            throw new ApiException(HttpStatus.CONFLICT, "RESOURCE_STATE_CONFLICT",
                    "A closed case cannot register a recording analysis job.");
        }

        SearchConditionRow condition = missingCaseMapper.findSearchCondition(caseId, request.conditionId());
        if (condition == null) {
            throw notFound("Search condition was not found.");
        }

        Recording recording = recordingMapper.findById(request.recordingId());
        if (recording == null) {
            throw notFound("Recording was not found.");
        }

        if (!missingCaseMapper.existsActiveCaseCamera(caseId, recording.getCameraId())) {
            throw new ApiException(HttpStatus.UNPROCESSABLE_ENTITY, "BUSINESS_RULE_VIOLATION",
                    "The recording camera is not enabled for this case.");
        }

        AnalysisJob job = new AnalysisJob();
        job.setCaseId(caseId);
        job.setSearchConditionId(condition.getId());
        job.setRecordingId(recording.getId());
        job.setJobType(RECORDING_ANALYSIS);
        job.setStatus(QUEUED);
        job.setPromptSnapshot(condition.getPrompt());
        job.setExclusionPromptSnapshot(condition.getExclusionPrompt());
        job.setSearchStartSnapshot(condition.getSearchStart());
        job.setSearchEndSnapshot(condition.getSearchEnd());
        job.setSearchAreaSnapshot(condition.getSearchArea());
        job.setSimilarityThresholdSnapshot(condition.getSimilarityThreshold());
        analysisJobMapper.insert(job);

        auditService.recordRequired("RECORDING_ANALYSIS_JOB_CREATED", adminId, caseId,
                "ANALYSIS_JOB", job.getId(),
                Map.of("conditionId", condition.getId(), "recordingId", recording.getId()));
        return RecordingAnalysisJobResponse.from(job);
    }

    private ApiException notFound(String message) {
        return new ApiException(HttpStatus.NOT_FOUND, "RESOURCE_NOT_FOUND", message);
    }
}
