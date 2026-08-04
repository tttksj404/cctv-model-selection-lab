package com.ssafy.eyesonu;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.ssafy.eyesonu.admin.mapper.AdminMapper;
import com.ssafy.eyesonu.audit.service.AuditService;
import com.ssafy.eyesonu.auth.config.SecurityConfig;
import com.ssafy.eyesonu.auth.device.MediaServerAuthenticationService;
import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.common.exception.GlobalExceptionHandler;
import com.ssafy.eyesonu.recording.controller.aiworker.AiWorkerJobController;
import com.ssafy.eyesonu.recording.dto.aiworker.AiWorkerClaimResponse;
import com.ssafy.eyesonu.recording.dto.aiworker.AiWorkerJobResponse;
import com.ssafy.eyesonu.recording.service.AiWorkerAuthenticationService;
import com.ssafy.eyesonu.recording.service.AiWorkerJobService;
import java.time.Instant;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import java.util.List;

@ActiveProfiles("test")
@WebMvcTest(controllers = AiWorkerJobController.class)
@Import({SecurityConfig.class, GlobalExceptionHandler.class})
class AiWorkerJobApiTests {

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private AdminMapper adminMapper;

    @MockitoBean
    private AuditService auditService;

    @MockitoBean
    private MediaServerAuthenticationService mediaServerAuthenticationService;

    @MockitoBean
    private AiWorkerAuthenticationService authenticationService;

    @MockitoBean
    private AiWorkerJobService jobService;

    @Test
    void workerClaimUsesDedicatedHeaderWithoutSessionOrCsrfToken() throws Exception {
        when(jobService.claim(any())).thenReturn(
                AiWorkerClaimResponse.empty("eyesonu-ai-worker-v1", 1000));

        mockMvc.perform(post("/api/v1/ai-worker/jobs/claim")
                        .header("X-AI-Worker-Key", "worker-key")
                        .header("X-AI-Worker-ID", "notebook-1")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"workerId":"notebook-1","modelKey":"fixture-v1"}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.schemaVersion").value("eyesonu-ai-worker-v1"))
                .andExpect(jsonPath("$.data.job").doesNotExist());

        verify(authenticationService).requireValidKey("worker-key");
    }

    @Test
    void missingWorkerKeyReachesWorkerAuthenticationInsteadOfSpringSecurity403() throws Exception {
        doThrow(new ApiException(
                HttpStatus.UNAUTHORIZED,
                "AI_WORKER_UNAUTHORIZED",
                "AI Worker authentication failed.")
        ).when(authenticationService).requireValidKey(null);

        mockMvc.perform(post("/api/v1/ai-worker/jobs/claim")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"workerId":"notebook-1","modelKey":"fixture-v1"}
                                """))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value("AI_WORKER_UNAUTHORIZED"));
    }

    @Test
    void workerClaimsTheRabbitMessageJobIdWithoutFallingBackToQueueWideClaim() throws Exception {
        when(jobService.claimJob(any(), any())).thenReturn(
                AiWorkerClaimResponse.empty("eyesonu-ai-worker-v1", 1000));

        mockMvc.perform(post("/api/v1/ai-worker/jobs/71/claim")
                        .header("X-AI-Worker-Key", "worker-key")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"workerId":"notebook-1","modelKey":"fixture-v1"}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.job").doesNotExist());

        verify(jobService).claimJob(71L, new com.ssafy.eyesonu.recording.dto.aiworker.AiWorkerClaimRequest(
                "notebook-1", "fixture-v1"));
    }

    @Test
    void workerClaimUsesDevContractWithoutSimilarityThreshold() throws Exception {
        Instant leaseExpiresAt = Instant.parse("2026-08-04T01:00:00Z");
        when(jobService.claimJob(any(), any())).thenReturn(new AiWorkerClaimResponse(
                "eyesonu-ai-worker-v1",
                new AiWorkerJobResponse(
                        "eyesonu-ai-worker-v1", 71L, 11L, 21L, 31L,
                        "fixture-v1", 41L, "Gate A", "CAM-001",
                        "https://storage.example/video.mp4", null,
                        Instant.parse("2026-08-04T00:00:00Z"),
                        Instant.parse("2026-08-04T00:30:00Z"),
                        "red jacket", null, 0L, 30_000L, leaseExpiresAt),
                "lease-1", leaseExpiresAt, 0));

        mockMvc.perform(post("/api/v1/ai-worker/jobs/71/claim")
                        .header("X-AI-Worker-Key", "worker-key")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"workerId":"notebook-1","modelKey":"fixture-v1"}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.job.prompt").value("red jacket"))
                .andExpect(jsonPath("$.data.job.similarityThreshold").doesNotExist());
    }

    @Test
    void workerRequestsLeaseBoundEvidenceUploadUrls() throws Exception {
        when(jobService.createEvidenceUploadUrls(eq(71L), any())).thenReturn(
                new com.ssafy.eyesonu.recording.dto.aiworker.AiWorkerEvidenceUploadUrlResponse(
                        "eyesonu-ai-worker-v1", 71L, 1, 900,
                        List.of(new com.ssafy.eyesonu.recording.dto.aiworker.AiWorkerEvidenceUploadUrlResponse.Upload(
                                "track-3",
                                "analysis/analysis-71/attempt-1/frames/frame.jpg",
                                "https://storage.example/frame",
                                "analysis/analysis-71/attempt-1/crops/crop.jpg",
                                "https://storage.example/crop"))));

        mockMvc.perform(post("/api/v1/ai-worker/jobs/71/evidence-upload-urls")
                        .header("X-AI-Worker-Key", "worker-key")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"workerId":"notebook-1","leaseToken":"lease-1","candidates":[
                                  {"candidateKey":"track-3","frameContentType":"image/jpeg","cropContentType":"image/jpeg"}
                                ]}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.jobId").value(71))
                .andExpect(jsonPath("$.data.uploads[0].candidateKey").value("track-3"));

        verify(authenticationService).requireValidKey("worker-key");
        verify(jobService).createEvidenceUploadUrls(eq(71L), any());
    }
}
