package com.ssafy.eyesonu.recording.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import com.ssafy.eyesonu.camera.mapper.CameraMapper;
import com.ssafy.eyesonu.common.config.properties.AiWorkerProperties;
import com.ssafy.eyesonu.common.config.properties.S3Properties;
import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.missingcase.service.CandidateEventObjectKeyFactory;
import com.ssafy.eyesonu.recording.domain.AnalysisJob;
import com.ssafy.eyesonu.recording.domain.Recording;
import com.ssafy.eyesonu.recording.dto.aiworker.AiWorkerCompleteRequest;
import com.ssafy.eyesonu.recording.dto.aiworker.AiWorkerFailRequest;
import com.ssafy.eyesonu.recording.dto.device.RecordingAnalysisBatchResultRequest;
import com.ssafy.eyesonu.recording.mapper.AnalysisJobMapper;
import com.ssafy.eyesonu.recording.mapper.RecordingMapper;
import com.ssafy.eyesonu.recording.messaging.RecordingAnalysisJobPublisher;
import com.ssafy.eyesonu.storage.StorageObjectUrlSigner;
import java.time.Duration;
import java.time.Instant;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import tools.jackson.databind.json.JsonMapper;

@ExtendWith(MockitoExtension.class)
class AiWorkerJobServiceTests {

    @Mock private AnalysisJobMapper analysisJobMapper;
    @Mock private RecordingMapper recordingMapper;
    @Mock private CameraMapper cameraMapper;
    @Mock private StorageObjectUrlSigner storageObjectUrlSigner;
    @Mock private RecordingAnalysisBatchResultService batchResultService;
    @Mock private RecordingAnalysisJobPublisher publisher;

    private AiWorkerJobService service;
    private CandidateEventObjectKeyFactory objectKeyFactory;

    @BeforeEach
    void setUp() {
        AiWorkerProperties properties = new AiWorkerProperties();
        properties.setLeaseDuration(Duration.ofSeconds(90));
        properties.setMaxRetryCount(3);
        objectKeyFactory = new CandidateEventObjectKeyFactory();
        service = new AiWorkerJobService(
                analysisJobMapper,
                recordingMapper,
                cameraMapper,
                storageObjectUrlSigner,
                objectKeyFactory,
                new S3Properties(),
                batchResultService,
                publisher,
                properties,
                JsonMapper.builder().findAndAddModules().build());
    }

    @Test
    void retryableFailureCreatesANewOutboxCommand() {
        AnalysisJob job = job(0);
        when(analysisJobMapper.findByIdForWorker(71L)).thenReturn(job);
        when(analysisJobMapper.fail(
                eq(71L), eq("notebook-1"), any(), eq("QUEUED"), any())).thenReturn(1);

        var response = service.fail(71L, new AiWorkerFailRequest(
                "notebook-1", "lease-1", "StorageError", "download interrupted", true));

        assertEquals("QUEUED", response.status());
        verify(publisher).enqueue(71L, 11L);
    }

    @Test
    void exhaustedFailureDoesNotCreateAnotherOutboxCommand() {
        AnalysisJob job = job(3);
        when(analysisJobMapper.findByIdForWorker(71L)).thenReturn(job);
        when(analysisJobMapper.fail(
                eq(71L), eq("notebook-1"), any(), eq("FAILED"), any())).thenReturn(1);

        var response = service.fail(71L, new AiWorkerFailRequest(
                "notebook-1", "lease-1", "ModelError", "invalid model", true));

        assertEquals("FAILED", response.status());
        verify(publisher, never()).enqueue(71L, 11L);
    }

    @Test
    void completionRejectsEvidenceKeysIssuedForAnotherCandidate() throws Exception {
        AnalysisJob job = job(0);
        when(analysisJobMapper.findByIdForWorker(71L)).thenReturn(job);
        String otherCandidateFrame = objectKeyFactory.analysisFrameKey(
                71L, 1, "track-other", "image/jpeg");
        String expectedCrop = objectKeyFactory.analysisCropKey(
                71L, 1, "track-1", "image/jpeg");
        var result = JsonMapper.builder().findAndAddModules().build().readTree("""
                {
                  "schemaVersion": "eyesonu-ai-worker-v1",
                  "modelKey": "hybrid-v1",
                  "inferenceDurationMs": 12,
                  "candidates": [{
                    "candidateKey": "track-1",
                    "frameOffsetMs": 100,
                    "similarity": 0.91,
                    "boundingBox": {"x": 1, "y": 2, "width": 30, "height": 40},
                    "frameObjectKey": "%s",
                    "cropObjectKey": "%s"
                  }]
                }
                """.formatted(otherCandidateFrame, expectedCrop));

        ApiException exception = assertThrows(ApiException.class, () -> service.complete(
                71L, new AiWorkerCompleteRequest("notebook-1", "lease-1", result)));

        assertEquals("AI_WORKER_RESULT_INVALID", exception.getCode());
        verifyNoInteractions(batchResultService);
    }

    @Test
    void completionProjectsExactCandidateEvidenceIntoBatchResult() throws Exception {
        AnalysisJob job = job(0);
        job.setRecordingId(301L);
        when(analysisJobMapper.findByIdForWorker(71L)).thenReturn(job);
        when(recordingMapper.findById(301L)).thenReturn(new Recording(
                301L,
                11L,
                Instant.parse("2026-08-04T00:00:00Z"),
                Instant.parse("2026-08-04T00:01:00Z"),
                "recordings/CAM-001/video.mp4",
                100L,
                null));
        String frameKey = objectKeyFactory.analysisFrameKey(71L, 1, "track-1", "image/jpeg");
        String cropKey = objectKeyFactory.analysisCropKey(71L, 1, "track-1", "image/jpeg");
        var result = JsonMapper.builder().findAndAddModules().build().readTree("""
                {
                  "schemaVersion": "eyesonu-ai-worker-v1",
                  "modelKey": "hybrid-v1",
                  "inferenceDurationMs": 12,
                  "candidates": [{
                    "candidateKey": "track-1",
                    "frameOffsetMs": 100,
                    "similarity": 0.91,
                    "boundingBox": {"x": 1, "y": 2, "width": 30, "height": 40},
                    "frameObjectKey": "%s",
                    "cropObjectKey": "%s"
                  }]
                }
                """.formatted(frameKey, cropKey));

        var response = service.complete(
                71L, new AiWorkerCompleteRequest("notebook-1", "lease-1", result));
        ArgumentCaptor<RecordingAnalysisBatchResultRequest> requestCaptor =
                ArgumentCaptor.forClass(RecordingAnalysisBatchResultRequest.class);

        assertEquals("SUCCEEDED", response.status());
        verify(batchResultService).completeFromAiWorker(
                eq(71L), requestCaptor.capture(), eq("notebook-1"), any(),
                eq("hybrid-v1"), any(), any());
        assertEquals("track-1", requestCaptor.getValue().candidates().getFirst().trackId());
        assertEquals(frameKey, requestCaptor.getValue().candidates().getFirst().frameObjectKey());
        assertEquals(cropKey, requestCaptor.getValue().candidates().getFirst().cropObjectKey());
    }

    private AnalysisJob job(int retryCount) {
        AnalysisJob job = new AnalysisJob();
        job.setId(71L);
        job.setCaseId(11L);
        job.setRetryCount(retryCount);
        return job;
    }
}
