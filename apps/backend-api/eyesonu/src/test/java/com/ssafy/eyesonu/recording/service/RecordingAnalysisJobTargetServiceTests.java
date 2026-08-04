package com.ssafy.eyesonu.recording.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.recording.domain.AnalysisJob;
import com.ssafy.eyesonu.recording.domain.RecordingAnalysisPublishSnapshot;
import com.ssafy.eyesonu.recording.mapper.AnalysisJobMapper;
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

    @Mock private AnalysisJobMapper analysisJobMapper;

    private RecordingAnalysisJobTargetService service;

    @BeforeEach
    void setUp() {
        service = new RecordingAnalysisJobTargetService(analysisJobMapper);
    }

    @Test
    void returnsPromptAndRecordingTargetForClaimedWorker() {
        AnalysisJob job = runningJob();
        RecordingAnalysisPublishSnapshot snapshot = snapshot();
        when(analysisJobMapper.findRecordingAnalysisById(JOB_ID)).thenReturn(job);
        when(analysisJobMapper.findRecordingAnalysisPublishSnapshot(JOB_ID, 101L)).thenReturn(snapshot);

        var response = service.find(JOB_ID, WORKER_ID);

        assertEquals(JOB_ID, response.jobId());
        assertEquals("recordings/CAM-001/video.mp4", response.recordingObjectKey());
        assertEquals("a person wearing a black short sleeve top and blue pants", response.prompt());
        assertEquals("a person wearing a red long sleeve top and black pants", response.exclusionPrompt());
        assertEquals(1, response.attempt());
    }

    @Test
    void rejectsWorkerThatDoesNotOwnTheJobLease() {
        when(analysisJobMapper.findRecordingAnalysisById(JOB_ID)).thenReturn(runningJob());

        ApiException exception = assertThrows(ApiException.class, () ->
                service.find(JOB_ID, "another-worker"));

        assertEquals("JOB_NOT_CLAIMED", exception.getCode());
        verify(analysisJobMapper, never()).findRecordingAnalysisPublishSnapshot(eq(JOB_ID), eq(101L));
    }

    private AnalysisJob runningJob() {
        AnalysisJob job = new AnalysisJob();
        job.setId(JOB_ID);
        job.setCaseId(101L);
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
        snapshot.setSearchStart(Instant.parse("2026-08-03T00:00:00Z"));
        snapshot.setSearchEnd(Instant.parse("2026-08-03T00:30:00Z"));
        snapshot.setSearchArea("front gate");
        snapshot.setAttempt(1);
        return snapshot;
    }
}
