package com.ssafy.eyesonu;

import static org.mockito.ArgumentMatchers.any;
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
import com.ssafy.eyesonu.recording.service.AiWorkerAuthenticationService;
import com.ssafy.eyesonu.recording.service.AiWorkerJobService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

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
}
