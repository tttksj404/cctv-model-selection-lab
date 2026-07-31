package com.ssafy.eyesonu;

import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.authentication;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.csrf;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.ssafy.eyesonu.admin.mapper.AdminMapper;
import com.ssafy.eyesonu.audit.service.AuditService;
import com.ssafy.eyesonu.auth.config.SecurityConfig;
import com.ssafy.eyesonu.auth.device.MediaServerAuthenticationService;
import com.ssafy.eyesonu.auth.security.AdminPrincipal;
import com.ssafy.eyesonu.camera.domain.CameraManagementRow;
import com.ssafy.eyesonu.camera.controller.admin.CameraController;
import com.ssafy.eyesonu.camera.dto.CameraDetailResponse;
import com.ssafy.eyesonu.camera.dto.CameraCreateRequest;
import com.ssafy.eyesonu.camera.dto.CameraListResponse;
import com.ssafy.eyesonu.camera.dto.CameraNamePatchRequest;
import com.ssafy.eyesonu.camera.dto.CameraPutRequest;
import com.ssafy.eyesonu.camera.service.CameraPageResult;
import com.ssafy.eyesonu.camera.service.CameraService;
import com.ssafy.eyesonu.common.exception.GlobalExceptionHandler;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.RequestPostProcessor;

@ActiveProfiles("test")
@WebMvcTest(controllers = CameraController.class)
@Import({SecurityConfig.class, GlobalExceptionHandler.class})
class CameraApiTests {

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private AdminMapper adminMapper;

    @MockitoBean
    private AuditService auditService;

    @MockitoBean
    private MediaServerAuthenticationService mediaServerAuthenticationService;

    @MockitoBean
    private CameraService cameraService;

    @Test
    void cameraListRequiresAdminSession() throws Exception {
        mockMvc.perform(get("/api/v1/admin/cameras"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value("AUTHENTICATION_REQUIRED"));
    }

    @Test
    void cameraListUsesPagedResponseAndDoesNotExposeRtspUrl() throws Exception {
        CameraListResponse response = CameraListResponse.from(row());
        when(cameraService.findAdminPage(null, null, 0, 20, "createdAt,desc"))
                .thenReturn(new CameraPageResult(List.of(response), 0, 20, 1L, 1, "createdAt,desc"));
        mockMvc.perform(get("/api/v1/admin/cameras").with(adminAuthentication()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data[0].cameraCode").value("CAM-001"))
                .andExpect(jsonPath("$.data[0].status").value("OFFLINE"))
                .andExpect(jsonPath("$.data[0].rtspUrl").doesNotExist())
                .andExpect(jsonPath("$.meta.page").value(0))
                .andExpect(jsonPath("$.meta.size").value(20));
    }

    @Test
    void cameraDetailReturnsResponseWithoutRtspUrl() throws Exception {
        when(cameraService.findAdminById(10L)).thenReturn(CameraDetailResponse.from(row()));
        mockMvc.perform(get("/api/v1/admin/cameras/10").with(adminAuthentication()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.id").value(10))
                .andExpect(jsonPath("$.data.cameraCode").value("CAM-001"))
                .andExpect(jsonPath("$.data.mediaServer.serverCode").value("MS-001"))
                .andExpect(jsonPath("$.data.rtspUrl").doesNotExist());

        verify(cameraService).findAdminById(10L);
    }

    @Test
    void cameraCreateWithoutCsrfReturnsAccessDenied() throws Exception {
        mockMvc.perform(post("/api/v1/admin/cameras")
                        .with(adminAuthentication())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(createBody()))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.code").value("ACCESS_DENIED"));
    }

    @Test
    void cameraCreateReturnsCreatedDetailWithOfflineStatus() throws Exception {
        CameraCreateRequest request = new CameraCreateRequest(
                20L,
                "CAM-001",
                "Front Gate",
                new BigDecimal("37.5"),
                new BigDecimal("127.0"),
                "Main address",
                "rtsp://secret.example/stream");
        when(cameraService.create(eq(1L), eq(request))).thenReturn(CameraDetailResponse.from(row()));
        mockMvc.perform(post("/api/v1/admin/cameras")
                        .with(adminAuthentication())
                        .with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(createBody()))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.data.status").value("OFFLINE"))
                .andExpect(jsonPath("$.data.rtspUrl").doesNotExist());

        verify(cameraService).create(eq(1L), eq(request));
    }

    @Test
    void cameraCreateRejectsUnsafePathCharactersInCameraCode() throws Exception {
        mockMvc.perform(post("/api/v1/admin/cameras")
                        .with(adminAuthentication())
                        .with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(createBody().replace("CAM-001", "front/gate")))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("VALIDATION_ERROR"))
                .andExpect(jsonPath("$.message").value(org.hamcrest.Matchers.containsString("cameraCode")));
    }

    @Test
    void cameraNamePatchReturnsUpdatedDetail() throws Exception {
        CameraDetailResponse response = CameraDetailResponse.from(row());
        CameraNamePatchRequest request = new CameraNamePatchRequest("Renamed");
        when(cameraService.patchName(eq(1L), eq(10L), eq(request))).thenReturn(response);
        mockMvc.perform(patch("/api/v1/admin/cameras/10/name")
                        .with(adminAuthentication())
                        .with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"cameraName\":\"Renamed\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.cameraCode").value("CAM-001"))
                .andExpect(jsonPath("$.data.status").value("OFFLINE"))
                .andExpect(jsonPath("$.data.rtspUrl").doesNotExist());

        verify(cameraService).patchName(eq(1L), eq(10L), eq(request));
    }

    @Test
    void cameraReplaceReturnsUpdatedDetail() throws Exception {
        CameraDetailResponse response = CameraDetailResponse.from(row());
        CameraPutRequest request = new CameraPutRequest(
                20L,
                "Updated",
                new BigDecimal("37.5"),
                new BigDecimal("127.0"),
                "Main address",
                "rtsp://secret.example/stream");
        when(cameraService.replace(eq(1L), eq(10L), eq(request))).thenReturn(response);
        mockMvc.perform(put("/api/v1/admin/cameras/10")
                        .with(adminAuthentication())
                        .with(csrf())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(putBody()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.cameraCode").value("CAM-001"))
                .andExpect(jsonPath("$.data.status").value("OFFLINE"))
                .andExpect(jsonPath("$.data.rtspUrl").doesNotExist());

        verify(cameraService).replace(eq(1L), eq(10L), eq(request));
    }

    @Test
    void cameraIdMustBePositive() throws Exception {
        mockMvc.perform(get("/api/v1/admin/cameras/0").with(adminAuthentication()))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("VALIDATION_ERROR"));
    }

    @Test
    void cameraNamePatchRequiresCsrf() throws Exception {
        mockMvc.perform(patch("/api/v1/admin/cameras/10/name")
                        .with(adminAuthentication())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"cameraName\":\"Renamed\"}"))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.code").value("ACCESS_DENIED"));
    }

    @Test
    void cameraReplaceRequiresCsrf() throws Exception {
        mockMvc.perform(put("/api/v1/admin/cameras/10")
                        .with(adminAuthentication())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(putBody()))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.code").value("ACCESS_DENIED"));
    }

    private RequestPostProcessor adminAuthentication() {
        AdminPrincipal principal = new AdminPrincipal(1L, "admin");
        return authentication(new UsernamePasswordAuthenticationToken(
                principal, null, principal.getAuthorities()));
    }

    private String createBody() {
        return """
                {
                  "mediaServerId": 20,
                  "cameraCode": "CAM-001",
                  "cameraName": "Front Gate",
                  "latitude": 37.5,
                  "longitude": 127.0,
                  "address": "Main address",
                  "rtspUrl": "rtsp://secret.example/stream"
                }
                """;
    }

    private String putBody() {
        return """
                {
                  "mediaServerId": 20,
                  "cameraName": "Updated",
                  "latitude": 37.5,
                  "longitude": 127.0,
                  "address": "Main address",
                  "rtspUrl": "rtsp://secret.example/stream"
                }
                """;
    }

    private CameraManagementRow row() {
        return new CameraManagementRow(
                10L, 20L, "MS-001", "Media Server", "CAM-001", "Front Gate",
                new BigDecimal("37.5000000"), new BigDecimal("127.0000000"), "Main address",
                "rtsp://secret.example/stream", "OFFLINE", null,
                Instant.parse("2026-07-28T00:00:00Z"), Instant.parse("2026-07-28T00:00:00Z"));
    }

}
