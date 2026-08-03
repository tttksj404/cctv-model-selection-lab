package com.ssafy.eyesonu.recording.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.ssafy.eyesonu.audit.service.AuditService;
import com.ssafy.eyesonu.recording.domain.AnalysisJob;
import com.ssafy.eyesonu.recording.domain.RecordingAnalysisResult;
import com.ssafy.eyesonu.recording.dto.device.RecordingAnalysisFailureRequest;
import com.ssafy.eyesonu.recording.mapper.AnalysisJobMapper;
import com.ssafy.eyesonu.recording.mapper.RecordingAnalysisResultMapper;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HexFormat;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class RecordingAnalysisFailureServiceTests {

    @Mock private AnalysisJobMapper jobMapper;
    @Mock private RecordingAnalysisResultMapper resultMapper;
    @Mock private AuditService auditService;

    private RecordingAnalysisFailureService service;

    @BeforeEach
    void setUp() {
        service = new RecordingAnalysisFailureService(jobMapper, resultMapper, auditService);
    }

    @Test
    void recordsFailureForRunningAttempt() {
        RecordingAnalysisFailureRequest request = request();
        when(jobMapper.findRecordingAnalysisByIdForUpdate(5001L)).thenReturn(job("RUNNING", 0));
        when(resultMapper.findByJobIdAndAttempt(5001L, 1)).thenReturn(null);
        when(jobMapper.markFailed(101L, 5001L, "VIDEO_DECODE_FAILED: broken stream")).thenReturn(1);

        var response = service.fail(5001L, request, "worker-1");

        assertEquals("FAILED", response.status());
        assertEquals(1, response.attempt());
        verify(resultMapper).insert(org.mockito.ArgumentMatchers.any(RecordingAnalysisResult.class));
    }

    @Test
    void acceptsIdenticalFailureRetry() throws Exception {
        RecordingAnalysisFailureRequest request = request();
        RecordingAnalysisResult existing = new RecordingAnalysisResult();
        existing.setResultId(request.resultId());
        existing.setPayloadHash(HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256")
                .digest(request.toString().getBytes(StandardCharsets.UTF_8))));
        existing.setStatus("FAILED");
        when(jobMapper.findRecordingAnalysisByIdForUpdate(5001L)).thenReturn(job("FAILED", 0));
        when(resultMapper.findByJobIdAndAttempt(5001L, 1)).thenReturn(existing);

        var response = service.fail(5001L, request, "worker-1");

        assertTrue(response.duplicate());
        verify(jobMapper, never()).markFailed(
                org.mockito.ArgumentMatchers.any(), org.mockito.ArgumentMatchers.any(),
                org.mockito.ArgumentMatchers.any());
    }

    @Test
    void usesNextAttemptAfterAdminRetry() {
        RecordingAnalysisFailureRequest request = request();
        when(jobMapper.findRecordingAnalysisByIdForUpdate(5001L)).thenReturn(job("RUNNING", 1));
        when(resultMapper.findByJobIdAndAttempt(5001L, 2)).thenReturn(null);
        when(jobMapper.markFailed(101L, 5001L, "VIDEO_DECODE_FAILED: broken stream")).thenReturn(1);

        var response = service.fail(5001L, request, "worker-1");

        assertEquals(2, response.attempt());
    }

    private AnalysisJob job(String status, int retryCount) {
        AnalysisJob job = new AnalysisJob();
        job.setId(5001L);
        job.setCaseId(101L);
        job.setStatus(status);
        job.setRetryCount(retryCount);
        return job;
    }

    private RecordingAnalysisFailureRequest request() {
        return new RecordingAnalysisFailureRequest(
                "failure-1", "VIDEO_DECODE_FAILED", "broken stream");
    }
}
