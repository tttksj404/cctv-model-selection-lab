package com.ssafy.eyesonu;

import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.authentication;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.ssafy.eyesonu.admin.domain.Admin;
import com.ssafy.eyesonu.admin.mapper.AdminMapper;
import com.ssafy.eyesonu.audit.service.AuditService;
import com.ssafy.eyesonu.auth.config.SecurityConfig;
import com.ssafy.eyesonu.auth.device.MediaServerAuthenticationService;
import com.ssafy.eyesonu.auth.security.AdminPrincipal;
import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.common.exception.GlobalExceptionHandler;
import com.ssafy.eyesonu.recording.controller.admin.AdminRecordingController;
import com.ssafy.eyesonu.recording.dto.admin.AdminRecordingCameraResponse;
import com.ssafy.eyesonu.recording.dto.admin.AdminRecordingDetailResponse;
import com.ssafy.eyesonu.recording.dto.admin.AdminRecordingListResponse;
import com.ssafy.eyesonu.recording.dto.admin.AdminRecordingSearchCondition;
import com.ssafy.eyesonu.recording.service.AdminRecordingPageResult;
import com.ssafy.eyesonu.recording.service.RecordingQueryService;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.HttpStatus;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.RequestPostProcessor;

@ActiveProfiles("test")
@WebMvcTest(controllers = AdminRecordingController.class)
@Import({SecurityConfig.class, GlobalExceptionHandler.class})
class AdminRecordingApiTests {

	private static final long ADMIN_ID = 1L;

	@Autowired
	private MockMvc mockMvc;

	@MockitoBean
	private AdminMapper adminMapper;

	@MockitoBean
	private AuditService auditService;

	@MockitoBean
	private MediaServerAuthenticationService mediaServerAuthenticationService;

	@MockitoBean
	private RecordingQueryService queryService;

	@BeforeEach
	void activeAdmin() {
		when(adminMapper.findById(ADMIN_ID))
				.thenReturn(Optional.of(new Admin(ADMIN_ID, "admin", "hash", "Admin")));
	}

	@Test
	void recordingListRequiresAdminAuthentication() throws Exception {
		mockMvc.perform(get("/api/v1/admin/recordings"))
				.andExpect(status().isUnauthorized())
				.andExpect(jsonPath("$.code").value("AUTHENTICATION_REQUIRED"));
	}

	@Test
	void recordingListReturnsPagedDataWithoutS3Key() throws Exception {
		AdminRecordingListResponse response = new AdminRecordingListResponse(
				201L,
				new AdminRecordingCameraResponse(11L, "CAM-001", "Front Gate"),
				Instant.parse("2026-07-20T01:00:00Z"),
				Instant.parse("2026-07-20T01:01:00Z"),
				80L,
				Instant.parse("2026-07-20T01:01:01Z"));
		AdminRecordingSearchCondition condition = new AdminRecordingSearchCondition(
				11L,
				OffsetDateTime.parse("2026-07-20T00:00:00Z"),
				OffsetDateTime.parse("2026-07-21T00:00:00Z"),
				0,
				20,
				"createdAt,desc");
		org.mockito.Mockito.when(queryService.findAll(org.mockito.ArgumentMatchers.eq(condition))).thenReturn(
				new AdminRecordingPageResult(List.of(response), 0, 20, 1L, 1, "createdAt,desc"));

		mockMvc.perform(get("/api/v1/admin/recordings")
					.with(adminAuthentication())
					.param("cameraId", "11")
					.param("startFrom", "2026-07-20T00:00:00Z")
					.param("startTo", "2026-07-21T00:00:00Z")
					.param("sort", "createdAt,desc"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data[0].id").value(201))
				.andExpect(jsonPath("$.data[0].camera.cameraCode").value("CAM-001"))
				.andExpect(jsonPath("$.data[0].fileSize").value(80))
				.andExpect(jsonPath("$.data[0].s3Key").doesNotExist())
				.andExpect(jsonPath("$.meta.totalElements").value(1))
				.andExpect(jsonPath("$.meta.sort").value("createdAt,desc"));

		verify(queryService).findAll(org.mockito.ArgumentMatchers.eq(condition));
	}

	@Test
	void recordingDetailReturnsVideoUrl() throws Exception {
		org.mockito.Mockito.when(queryService.findById(201L)).thenReturn(
				new AdminRecordingDetailResponse(
						201L,
						new AdminRecordingCameraResponse(11L, "CAM-001", "Front Gate"),
						Instant.parse("2026-07-20T01:00:00Z"),
						Instant.parse("2026-07-20T01:01:00Z"),
						80L,
						"https://storage.example/video.mp4",
						Instant.parse("2026-07-20T01:01:01Z")));

		mockMvc.perform(get("/api/v1/admin/recordings/201").with(adminAuthentication()))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.id").value(201))
				.andExpect(jsonPath("$.data.videoUrl").value("https://storage.example/video.mp4"))
				.andExpect(jsonPath("$.data.s3Key").doesNotExist());
	}

	@Test
	void recordingDetailNotFoundReturnsStructuredError() throws Exception {
		org.mockito.Mockito.when(queryService.findById(404L)).thenThrow(
				new ApiException(HttpStatus.NOT_FOUND, "RESOURCE_NOT_FOUND", "Recording was not found"));

		mockMvc.perform(get("/api/v1/admin/recordings/404").with(adminAuthentication()))
				.andExpect(status().isNotFound())
				.andExpect(jsonPath("$.code").value("RESOURCE_NOT_FOUND"));
	}

	@Test
	void recordingDetailStorageFailureReturnsServiceUnavailable() throws Exception {
		org.mockito.Mockito.when(queryService.findById(503L)).thenThrow(
				new ApiException(HttpStatus.SERVICE_UNAVAILABLE, "STORAGE_UNAVAILABLE", "Video URL unavailable"));

		mockMvc.perform(get("/api/v1/admin/recordings/503").with(adminAuthentication()))
				.andExpect(status().isServiceUnavailable())
				.andExpect(jsonPath("$.code").value("STORAGE_UNAVAILABLE"));
	}

	@Test
	void nonPositiveRecordingIdReturnsValidationError() throws Exception {
		mockMvc.perform(get("/api/v1/admin/recordings/0").with(adminAuthentication()))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("VALIDATION_ERROR"));
	}

	private RequestPostProcessor adminAuthentication() {
		AdminPrincipal principal = new AdminPrincipal(ADMIN_ID, "admin");
		return authentication(new UsernamePasswordAuthenticationToken(
				principal, null, principal.getAuthorities()));
	}
}
