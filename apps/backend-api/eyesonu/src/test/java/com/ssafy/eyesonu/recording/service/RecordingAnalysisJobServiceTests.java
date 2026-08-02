package com.ssafy.eyesonu.recording.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

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
import com.ssafy.eyesonu.recording.mapper.AnalysisJobMapper;
import com.ssafy.eyesonu.recording.mapper.RecordingMapper;
import com.ssafy.eyesonu.recording.messaging.RecordingAnalysisJobPublisher;
import com.ssafy.eyesonu.storage.StorageObject;
import com.ssafy.eyesonu.storage.StorageObjectVerifier;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.dao.DuplicateKeyException;

@ExtendWith(MockitoExtension.class)
class RecordingAnalysisJobServiceTests {

    private static final long CASE_ID = 101L;
    private static final long CONDITION_ID = 10L;
    private static final long RECORDING_ID = 3001L;
    private static final long CAMERA_ID = 2L;

    @Mock private AnalysisJobMapper analysisJobMapper;
    @Mock private MissingCaseMapper missingCaseMapper;
    @Mock private CaseQueryService caseQueryService;
    @Mock private RecordingMapper recordingMapper;
    @Mock private StorageObjectVerifier storageObjectVerifier;
    @Mock private AuditService auditService;
    @Mock private RecordingAnalysisJobPublisher recordingAnalysisJobPublisher;

    private RecordingAnalysisJobService service;

    @BeforeEach
    void setUp() {
        service = new RecordingAnalysisJobService(
                analysisJobMapper, missingCaseMapper, caseQueryService,
                recordingMapper, storageObjectVerifier, auditService,
                recordingAnalysisJobPublisher);
    }

    @Test
    void rejectsClosedCaseBeforeLoadingAnalysisTarget() {
        when(caseQueryService.require(CASE_ID)).thenReturn(caseWithStatus(CaseStatus.CLOSED));

        assertThrows(ApiException.class, () -> service.create(CASE_ID, request(), 1L));

        verifyNoInteractions(missingCaseMapper, recordingMapper, storageObjectVerifier, analysisJobMapper);
    }

    @Test
    void rejectsExistingActiveJob() {
        when(caseQueryService.require(CASE_ID)).thenReturn(caseWithStatus(CaseStatus.SEARCHING));
        when(missingCaseMapper.findSearchCondition(CASE_ID, CONDITION_ID)).thenReturn(condition());
        when(recordingMapper.findById(RECORDING_ID)).thenReturn(recording());
        when(analysisJobMapper.findActiveByTarget(CASE_ID, CONDITION_ID, RECORDING_ID))
                .thenReturn(new AnalysisJob());

        assertThrows(ApiException.class, () -> service.create(CASE_ID, request(), 1L));

        verify(analysisJobMapper, never()).insert(any());
        verifyNoInteractions(storageObjectVerifier);
    }

    @Test
    void mapsConcurrentUniqueKeyCollisionToConflict() {
        prepareValidTarget();
        when(analysisJobMapper.insert(any())).thenThrow(new DuplicateKeyException("duplicate"));

        assertThrows(ApiException.class, () -> service.create(CASE_ID, request(), 1L));
    }

    @Test
    void returnsOnlyRequestedRecordingAnalysisJob() {
        AnalysisJob job = new AnalysisJob();
        job.setId(5001L);
        job.setCaseId(CASE_ID);
        job.setJobType("RECORDING_ANALYSIS");
        job.setStatus("QUEUED");
        when(analysisJobMapper.findById(CASE_ID, 5001L)).thenReturn(job);

        var response = service.findById(CASE_ID, 5001L);

        assertEquals(5001L, response.jobId());
        assertEquals("RECORDING_ANALYSIS", response.jobType());
    }

    @Test
    void returnsRecordingAnalysisJobsForDashboardCases() {
        AnalysisJob job = new AnalysisJob();
        job.setId(5001L);
        job.setCaseId(CASE_ID);
        job.setJobType("RECORDING_ANALYSIS");
        job.setStatus("QUEUED");
        when(analysisJobMapper.findRecordingAnalysisByCaseIds(List.of(CASE_ID, 202L)))
                .thenReturn(List.of(job));

        var response = service.findAllForDashboard(List.of(CASE_ID, 202L));

        assertEquals(1, response.size());
        assertEquals(5001L, response.getFirst().jobId());
        verify(analysisJobMapper).findRecordingAnalysisByCaseIds(List.of(CASE_ID, 202L));
    }

    @Test
    void cancelsOnlyQueuedOrRunningJob() {
        AnalysisJob job = new AnalysisJob();
        job.setId(5001L);
        job.setCaseId(CASE_ID);
        job.setStatus("RUNNING");
        when(analysisJobMapper.findById(CASE_ID, 5001L)).thenReturn(job);
        when(analysisJobMapper.cancelActive(CASE_ID, 5001L)).thenReturn(1);

        var response = service.cancel(CASE_ID, 5001L, 7L);

        assertEquals("RUNNING", job.getStatus());
        assertEquals(5001L, response.jobId());
        verify(auditService).recordRequired(
                "RECORDING_ANALYSIS_JOB_CANCELLED", 7L, CASE_ID, "ANALYSIS_JOB", 5001L, java.util.Map.of());
    }

    @Test
    void rejectsRetryWhenJobIsNotFailed() {
        AnalysisJob job = new AnalysisJob();
        job.setId(5001L);
        job.setCaseId(CASE_ID);
        job.setStatus("SUCCEEDED");
        when(analysisJobMapper.findById(CASE_ID, 5001L)).thenReturn(job);
        when(analysisJobMapper.retryFailed(CASE_ID, 5001L)).thenReturn(0);

        assertThrows(ApiException.class, () -> service.retry(CASE_ID, 5001L, 7L));
        verifyNoInteractions(auditService, recordingAnalysisJobPublisher);
    }

    private void prepareValidTarget() {
        when(caseQueryService.require(CASE_ID)).thenReturn(caseWithStatus(CaseStatus.SEARCHING));
        when(missingCaseMapper.findSearchCondition(CASE_ID, CONDITION_ID)).thenReturn(condition());
        when(recordingMapper.findById(RECORDING_ID)).thenReturn(recording());
        when(storageObjectVerifier.stat("recordings/CAM-001/video.mp4"))
                .thenReturn(new StorageObject(1024L, "video/mp4"));
        when(missingCaseMapper.existsActiveCaseCamera(CASE_ID, CAMERA_ID)).thenReturn(true);
    }

    private MissingCaseRow caseWithStatus(CaseStatus status) {
        MissingCaseRow row = new MissingCaseRow();
        row.setId(CASE_ID);
        row.setStatus(status);
        return row;
    }

    private SearchConditionRow condition() {
        SearchConditionRow row = new SearchConditionRow();
        row.setId(CONDITION_ID);
        row.setCaseId(CASE_ID);
        row.setPrompt("black shirt and blue pants");
        row.setSimilarityThreshold(new BigDecimal("0.72"));
        return row;
    }

    private Recording recording() {
        return new Recording(RECORDING_ID, CAMERA_ID,
                Instant.parse("2026-07-30T00:00:00Z"),
                Instant.parse("2026-07-30T01:00:00Z"),
                "recordings/CAM-001/video.mp4", 1024L,
                Instant.parse("2026-07-30T01:01:00Z"));
    }

    private RecordingAnalysisJobCreateRequest request() {
        return new RecordingAnalysisJobCreateRequest(CONDITION_ID, RECORDING_ID);
    }
}
