package com.ssafy.eyesonu.recording.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.recording.domain.AnalysisJob;
import com.ssafy.eyesonu.recording.domain.Recording;
import com.ssafy.eyesonu.recording.domain.RecordingAnalysisPublishSnapshot;
import com.ssafy.eyesonu.recording.mapper.AnalysisJobMapper;
import com.ssafy.eyesonu.recording.mapper.RecordingMapper;
import com.ssafy.eyesonu.storage.StorageObjectUrlSigner;
import java.time.Instant;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class RecordingAnalysisJobTargetServiceTests {

    private static final long JOB_ID = 42L;
    private static final String WORKER_ID = "recording-ai-worker";
    private static final String CLAIM_TOKEN = "claim-token-42";

    @Mock private AnalysisJobMapper analysisJobMapper;
    @Mock private RecordingMapper recordingMapper;
    @Mock private StorageObjectUrlSigner urlSigner;
    @Mock private RecordingAnalysisJobClaimService claimService;

    private RecordingAnalysisJobTargetService service;

    @BeforeEach
    void setUp() {
        service = new RecordingAnalysisJobTargetService(
                analysisJobMapper, recordingMapper, urlSigner, claimService);
    }

    @Test
    void returnsPromptAndRecordingTargetForClaimedWorker() {
        AnalysisJob job = runningJob();
        RecordingAnalysisPublishSnapshot snapshot = snapshot();
        when(claimService.requireActiveWorkerJob(JOB_ID, WORKER_ID, CLAIM_TOKEN)).thenReturn(job);
        when(analysisJobMapper.findRecordingAnalysisPublishSnapshot(JOB_ID, 101L)).thenReturn(snapshot);
        when(recordingMapper.findById(3001L)).thenReturn(recording());
        when(urlSigner.createGetUrl("recordings/CAM-001/video.mp4"))
                .thenReturn("https://storage.example/signed/video.mp4");

        var response = service.find(JOB_ID, WORKER_ID, CLAIM_TOKEN);

        assertEquals(JOB_ID, response.jobId());
        assertEquals(201L, response.searchConditionId());
        assertEquals("recordings/CAM-001/video.mp4", response.recordingObjectKey());
        assertEquals("https://storage.example/signed/video.mp4", response.recordingDownloadUrl());
        assertEquals(Instant.parse("2026-08-03T00:00:00Z"), response.recordingStart());
        assertEquals(Instant.parse("2026-08-03T01:00:00Z"), response.recordingEnd());
        assertEquals(600_000L, response.searchFromMs());
        assertEquals(1_800_000L, response.searchToMs());
        assertEquals("a person wearing a black short sleeve top and blue pants", response.prompt());
        assertEquals("a person wearing a red long sleeve top and black pants", response.exclusionPrompt());
        assertEquals(1, response.attempt());
    }

    @Test
    void rejectsWorkerThatDoesNotOwnTheJobLease() {
        when(claimService.requireActiveWorkerJob(JOB_ID, "another-worker", CLAIM_TOKEN))
                .thenThrow(new ApiException(org.springframework.http.HttpStatus.CONFLICT,
                        "WORKER_LEASE_CONFLICT", "Worker lease is not valid."));

        ApiException exception = assertThrows(ApiException.class, () ->
                service.find(JOB_ID, "another-worker", CLAIM_TOKEN));

        assertEquals("WORKER_LEASE_CONFLICT", exception.getCode());
        verify(analysisJobMapper, never()).findRecordingAnalysisPublishSnapshot(eq(JOB_ID), eq(101L));
    }

    private AnalysisJob runningJob() {
        AnalysisJob job = new AnalysisJob();
        job.setId(JOB_ID);
        job.setCaseId(101L);
        job.setSearchConditionId(201L);
        job.setStatus("RUNNING");
        job.setClaimedBy(WORKER_ID);
        return job;
    }

    private RecordingAnalysisPublishSnapshot snapshot() {
        RecordingAnalysisPublishSnapshot snapshot = new RecordingAnalysisPublishSnapshot();
        snapshot.setJobId(JOB_ID);
        snapshot.setCaseId(101L);
        snapshot.setRecordingId(3001L);
        snapshot.setCameraId(11L);
        snapshot.setCameraCode("CAM-001");
        snapshot.setCameraName("Front");
        snapshot.setRecordingObjectKey("recordings/CAM-001/video.mp4");
        snapshot.setPrompt("a person wearing a black short sleeve top and blue pants");
        snapshot.setExclusionPrompt("a person wearing a red long sleeve top and black pants");
        snapshot.setSearchStart(Instant.parse("2026-08-03T00:10:00Z"));
        snapshot.setSearchEnd(Instant.parse("2026-08-03T00:30:00Z"));
        snapshot.setSearchArea("front gate");
        snapshot.setAttempt(1);
        return snapshot;
    }

    private Recording recording() {
        return new Recording(
                3001L,
                11L,
                Instant.parse("2026-08-03T00:00:00Z"),
                Instant.parse("2026-08-03T01:00:00Z"),
                "recordings/CAM-001/video.mp4",
                1024L,
                Instant.parse("2026-08-03T01:01:00Z"));
    }
}
