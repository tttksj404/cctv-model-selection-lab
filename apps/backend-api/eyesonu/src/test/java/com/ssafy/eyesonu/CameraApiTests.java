package com.ssafy.eyesonu;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.ssafy.eyesonu.admin.domain.Admin;
import com.ssafy.eyesonu.admin.mapper.AdminMapper;
import com.ssafy.eyesonu.audit.mapper.AuditLogMapper;
import com.ssafy.eyesonu.camera.domain.CameraManagementRow;
import com.ssafy.eyesonu.camera.dto.CameraDetailResponse;
import com.ssafy.eyesonu.camera.dto.CameraListResponse;
import com.ssafy.eyesonu.camera.service.CameraPageResult;
import com.ssafy.eyesonu.camera.service.CameraService;
import com.ssafy.eyesonu.caseinquiry.mapper.CaseInquiryMapper;
import com.ssafy.eyesonu.recording.service.RecordingQueryService;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.http.MediaType;
import org.springframework.mock.web.MockHttpSession;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import jakarta.servlet.http.Cookie;

@ActiveProfiles("test")
@SpringBootTest(useMainMethod = SpringBootTest.UseMainMethod.ALWAYS)
@AutoConfigureMockMvc
class CameraApiTests {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private PasswordEncoder passwordEncoder;

    @MockitoBean
    private AdminMapper adminMapper;

    @MockitoBean
    private AuditLogMapper auditLogMapper;

    @MockitoBean
    private CaseInquiryMapper caseInquiryMapper;

    @MockitoBean
    private RecordingQueryService recordingQueryService;

    @MockitoBean
    private CameraService cameraService;

    @BeforeEach
    void setUp() {
        Admin admin = new Admin(1L, "admin", passwordEncoder.encode("correct-password!"), "Administrator");
        when(adminMapper.findByLoginId("admin")).thenReturn(java.util.Optional.of(admin));
        when(adminMapper.findById(1L)).thenReturn(java.util.Optional.of(admin));
    }

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
        MockHttpSession session = login();

        mockMvc.perform(get("/api/v1/admin/cameras").session(session))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data[0].cameraCode").value("CAM-001"))
                .andExpect(jsonPath("$.data[0].status").value("OFFLINE"))
                .andExpect(jsonPath("$.data[0].rtspUrl").doesNotExist())
                .andExpect(jsonPath("$.meta.page").value(0))
                .andExpect(jsonPath("$.meta.size").value(20));
    }

    @Test
    void cameraCreateWithoutCsrfReturnsAccessDenied() throws Exception {
        MockHttpSession session = login();

        mockMvc.perform(post("/api/v1/admin/cameras")
                        .session(session)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(createBody()))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.code").value("ACCESS_DENIED"));
    }

    @Test
    void cameraCreateReturnsCreatedDetailWithOfflineStatus() throws Exception {
        when(cameraService.create(any(), any())).thenReturn(CameraDetailResponse.from(row()));
        LoginResult login = loginWithCsrf();

        mockMvc.perform(post("/api/v1/admin/cameras")
                        .session(login.session())
                        .cookie(login.csrfCookie())
                        .header("X-XSRF-TOKEN", login.csrfCookie().getValue())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(createBody()))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.data.status").value("OFFLINE"))
                .andExpect(jsonPath("$.data.rtspUrl").doesNotExist());
    }

    @Test
    void patchAndPutAreProtectedByCsrf() throws Exception {
        MockHttpSession session = login();
        mockMvc.perform(patch("/api/v1/admin/cameras/10/name")
                        .session(session)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"cameraName\":\"Renamed\"}"))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.code").value("ACCESS_DENIED"));

        mockMvc.perform(put("/api/v1/admin/cameras/10")
                        .session(session)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(putBody()))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.code").value("ACCESS_DENIED"));
    }

    private MockHttpSession login() throws Exception {
        return loginWithCsrf().session();
    }

    private LoginResult loginWithCsrf() throws Exception {
        MvcResult csrfResult = mockMvc.perform(get("/api/v1/auth/csrf")).andReturn();
        Cookie csrfCookie = csrfResult.getResponse().getCookie("XSRF-TOKEN");
        MvcResult login = mockMvc.perform(post("/api/v1/auth/admin/login")
                        .cookie(csrfCookie)
                        .header("X-XSRF-TOKEN", csrfCookie.getValue())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"loginId\":\"admin\",\"password\":\"correct-password!\"}"))
                .andExpect(status().isOk())
                .andReturn();
        return new LoginResult((MockHttpSession) login.getRequest().getSession(false), csrfCookie);
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

    private record LoginResult(MockHttpSession session, Cookie csrfCookie) {
    }
}
