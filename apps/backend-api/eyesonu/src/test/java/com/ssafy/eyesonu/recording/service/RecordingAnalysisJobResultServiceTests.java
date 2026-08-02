package com.ssafy.eyesonu.recording.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.ssafy.eyesonu.auth.device.MediaServerPrincipal;
import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.missingcase.dto.device.CandidateEventCreateRequest;
import com.ssafy.eyesonu.missingcase.dto.device.CandidateEventCreateResponse;
import com.ssafy.eyesonu.missingcase.service.CandidateEventCommandService;
import com.ssafy.eyesonu.recording.domain.AnalysisJob;
import com.ssafy.eyesonu.recording.mapper.AnalysisJobMapper;
import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class RecordingAnalysisJobResultServiceTests {

    private static final long JOB_ID = 5001L;
    private static final long CASE_ID = 101L;

    @Mock private AnalysisJobMapper analysisJobMapper;
    @Mock private CandidateEventCommandService candidateEventCommandService;

    private RecordingAnalysisJobResultService service;

    @BeforeEach
    void setUp() {
        service = new RecordingAnalysisJobResultService(analysisJobMapper, candidateEventCommandService);
    }

    @Test
    void storesCandidatesAndMarksRunningJobSucceeded() {
        AnalysisJob running = job("RUNNING");
        AnalysisJob completed = job("SUCCEEDED");
        CandidateEventCreateRequest request = request(CASE_ID);
        CandidateEventCreateResponse candidateResult = new CandidateEventCreateResponse(
                "event-1", CASE_ID, 2L, 1, List.of(9001L), false, null);
        when(analysisJobMapper.findRecordingAnalysisById(JOB_ID)).thenReturn(running, completed);
        when(candidateEventCommandService.create(new MediaServerPrincipal(2L, "CAM-001"), request))
                .thenReturn(candidateResult);
        when(analysisJobMapper.markSucceeded(CASE_ID, JOB_ID)).thenReturn(1);

        var response = service.complete(new MediaServerPrincipal(2L, "CAM-001"), JOB_ID, request);

        assertEquals("SUCCEEDED", response.job().status());
        assertEquals(List.of(9001L), response.candidateResult().candidateIds());
        verify(analysisJobMapper).markSucceeded(CASE_ID, JOB_ID);
    }

    @Test
    void rejectsResultForDifferentCase() {
        when(analysisJobMapper.findRecordingAnalysisById(JOB_ID)).thenReturn(job("RUNNING"));

        assertThrows(ApiException.class, () -> service.complete(
                new MediaServerPrincipal(2L, "CAM-001"), JOB_ID, request(202L)));

        verify(candidateEventCommandService, never()).create(
                new MediaServerPrincipal(2L, "CAM-001"), request(202L));
        verify(analysisJobMapper, never()).markSucceeded(CASE_ID, JOB_ID);
    }

    @Test
    void rejectsResultWhenJobIsNotRunning() {
        when(analysisJobMapper.findRecordingAnalysisById(JOB_ID)).thenReturn(job("SUCCEEDED"));

        assertThrows(ApiException.class, () -> service.complete(
                new MediaServerPrincipal(2L, "CAM-001"), JOB_ID, request(CASE_ID)));

        verify(candidateEventCommandService, never()).create(
                new MediaServerPrincipal(2L, "CAM-001"), request(CASE_ID));
    }

    private AnalysisJob job(String status) {
        AnalysisJob job = new AnalysisJob();
        job.setId(JOB_ID);
        job.setCaseId(CASE_ID);
        job.setJobType("RECORDING_ANALYSIS");
        job.setStatus(status);
        return job;
    }

    private CandidateEventCreateRequest request(Long caseId) {
        return new CandidateEventCreateRequest(
                caseId, "CAM-001", "event-1", OffsetDateTime.parse("2026-08-02T10:00:00Z"),
                "frames/frame.jpg", List.of(new CandidateEventCreateRequest.Detection(
                        "track-1", new BigDecimal("0.91"), "crops/crop.jpg",
                        new CandidateEventCreateRequest.BoundingBox(1, 2, 30, 40))));
    }
}
