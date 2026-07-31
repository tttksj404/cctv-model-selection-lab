package com.ssafy.eyesonu;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.authentication;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.csrf;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
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
import com.ssafy.eyesonu.missingcase.domain.CaseStatus;
import com.ssafy.eyesonu.missingcase.domain.Gender;
import com.ssafy.eyesonu.missingcase.controller.AdminCaseController;
import com.ssafy.eyesonu.missingcase.dto.admin.AppearanceResponse;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseDetailResponse;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseListResponse;
import com.ssafy.eyesonu.missingcase.dto.admin.CasePhotoResponse;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseStateResponse;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseCloseRequest;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseStatusUpdateRequest;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseUpdateRequest;
import com.ssafy.eyesonu.missingcase.dto.admin.ReporterResponse;
import com.ssafy.eyesonu.missingcase.service.CaseCommandService;
import com.ssafy.eyesonu.missingcase.service.CasePageResult;
import com.ssafy.eyesonu.missingcase.service.CasePhotoService;
import com.ssafy.eyesonu.missingcase.service.CaseQueryService;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseSearchCondition;
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
import org.springframework.http.MediaType;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.RequestPostProcessor;

@ActiveProfiles("test")
@WebMvcTest(controllers = AdminCaseController.class)
@Import({SecurityConfig.class, GlobalExceptionHandler.class})
class AdminCaseApiTests {

	private static final long ADMIN_ID = 1L;
	private static final String CASE_NUMBER = "EFU-0123456789ABCDEFGHJKMNPQRS";

	@Autowired
	private MockMvc mockMvc;

	@MockitoBean
	private AdminMapper adminMapper;

	@MockitoBean
	private AuditService auditService;

	@MockitoBean
	private MediaServerAuthenticationService mediaServerAuthenticationService;

	@MockitoBean
	private CaseCommandService commandService;

	@MockitoBean
	private CaseQueryService queryService;

	@MockitoBean
	private CasePhotoService photoService;

	@BeforeEach
	void activeAdmin() {
		when(adminMapper.findById(ADMIN_ID))
				.thenReturn(Optional.of(new Admin(ADMIN_ID, "admin", "hash", "Admin")));
	}

	@Test
	void caseListRequiresAdminAuthentication() throws Exception {
		mockMvc.perform(get("/api/v1/admin/cases"))
				.andExpect(status().isUnauthorized())
				.andExpect(jsonPath("$.code").value("AUTHENTICATION_REQUIRED"));
	}

	@Test
	void caseListReturnsPagedResponseWithFilters() throws Exception {
		CaseListResponse response = new CaseListResponse(
				101L,
				CASE_NUMBER,
				CaseStatus.SEARCHING,
				"Missing",
				Gender.UNKNOWN,
				2000,
				null,
				Instant.parse("2026-07-20T00:00:00Z"),
				"Seoul",
				Instant.parse("2026-07-20T01:00:00Z"),
				Instant.parse("2026-07-20T02:00:00Z"));
		CaseSearchCondition condition = new CaseSearchCondition(
				CaseStatus.SEARCHING,
				CASE_NUMBER.toLowerCase(),
				"Missing",
				OffsetDateTime.parse("2026-07-19T00:00:00Z"),
				OffsetDateTime.parse("2026-07-21T00:00:00Z"),
				1,
				10,
				"updatedAt,asc");
		org.mockito.Mockito.when(queryService.findAll(eq(condition))).thenReturn(
				new CasePageResult(List.of(response), 1, 10, 11L, 2, "updatedAt,asc"));

		mockMvc.perform(get("/api/v1/admin/cases")
					.with(adminAuthentication())
					.param("status", "SEARCHING")
					.param("caseNumber", CASE_NUMBER.toLowerCase())
					.param("missingName", "Missing")
					.param("reportedFrom", "2026-07-19T00:00:00Z")
					.param("reportedTo", "2026-07-21T00:00:00Z")
					.param("page", "1")
					.param("size", "10")
					.param("sort", "updatedAt,asc"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data[0].id").value(101))
				.andExpect(jsonPath("$.data[0].caseNumber").value(CASE_NUMBER))
				.andExpect(jsonPath("$.meta.page").value(1))
				.andExpect(jsonPath("$.meta.size").value(10))
				.andExpect(jsonPath("$.meta.totalElements").value(11))
				.andExpect(jsonPath("$.meta.sort").value("updatedAt,asc"));

		verify(queryService).findAll(eq(condition));
	}

	@Test
	void caseDetailReturnsFullResponse() throws Exception {
		org.mockito.Mockito.when(queryService.findById(101L)).thenReturn(caseDetail());

		mockMvc.perform(get("/api/v1/admin/cases/101").with(adminAuthentication()))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.id").value(101))
				.andExpect(jsonPath("$.data.caseNumber").value(CASE_NUMBER))
				.andExpect(jsonPath("$.data.reporter.name").value("Reporter"))
				.andExpect(jsonPath("$.data.appearance.upperClothing").value("Coat"));
	}

	@Test
	void caseDetailNotFoundReturnsStructuredError() throws Exception {
		org.mockito.Mockito.when(queryService.findById(404L)).thenThrow(
				new ApiException(HttpStatus.NOT_FOUND, "RESOURCE_NOT_FOUND", "Case was not found"));

		mockMvc.perform(get("/api/v1/admin/cases/404").with(adminAuthentication()))
				.andExpect(status().isNotFound())
				.andExpect(jsonPath("$.code").value("RESOURCE_NOT_FOUND"));
	}

	@Test
	void caseListRejectsNegativePage() throws Exception {
		mockMvc.perform(get("/api/v1/admin/cases")
					.with(adminAuthentication())
					.param("page", "-1"))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("VALIDATION_ERROR"));
	}

	@Test
	void caseListRejectsOversizedPage() throws Exception {
		mockMvc.perform(get("/api/v1/admin/cases")
					.with(adminAuthentication())
					.param("size", "101"))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("VALIDATION_ERROR"));
	}

	@Test
	void caseUpdateReturnsUpdatedDetailAndPassesAdminId() throws Exception {
		org.mockito.Mockito.when(queryService.findById(101L)).thenReturn(caseDetail());

		mockMvc.perform(patch("/api/v1/admin/cases/101")
					.with(adminAuthentication())
					.with(csrf())
					.contentType(MediaType.APPLICATION_JSON)
					.content("""
						{"missingName":"Updated Missing","lastSeenAddress":"Updated address"}
						"""))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.id").value(101));

		verify(commandService).update(eq(101L),
				org.mockito.ArgumentMatchers.argThat((CaseUpdateRequest update) ->
						update.hasMissingName()
								&& "Updated Missing".equals(update.getMissingName())
								&& update.hasLastSeenAddress()
								&& "Updated address".equals(update.getLastSeenAddress())),
				eq(ADMIN_ID));
		verify(queryService).findById(101L);
	}

	@Test
	void photoPutReturnsPhotoUrl() throws Exception {
		org.mockito.Mockito.when(photoService.put(eq(101L), any(), eq(ADMIN_ID)))
				.thenReturn(new CasePhotoResponse("https://storage.example/case-photo.jpg"));
		MockMultipartFile photo = new MockMultipartFile(
				"photo", "photo.jpg", MediaType.IMAGE_JPEG_VALUE, new byte[] {1, 2, 3});

		mockMvc.perform(multipart("/api/v1/admin/cases/101/photo")
					.file(photo)
					.with(adminAuthentication())
					.with(csrf())
					.with(request -> {
						request.setMethod("PUT");
						return request;
					}))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.photoUrl").value("https://storage.example/case-photo.jpg"));

	}

	@Test
	void photoDeleteReturnsNoContent() throws Exception {
		mockMvc.perform(delete("/api/v1/admin/cases/101/photo")
					.with(adminAuthentication())
					.with(csrf()))
				.andExpect(status().isNoContent());

		verify(photoService).delete(101L, ADMIN_ID);
	}

	@Test
	void statusUpdateReturnsNewState() throws Exception {
		CaseStatusUpdateRequest request = new CaseStatusUpdateRequest(CaseStatus.SEARCHING, "Begin search");
		org.mockito.Mockito.when(commandService.updateStatus(eq(101L), eq(request), eq(ADMIN_ID)))
				.thenReturn(new CaseStateResponse(101L, CaseStatus.SEARCHING, null,
						Instant.parse("2026-07-20T02:00:00Z")));

		mockMvc.perform(patch("/api/v1/admin/cases/101/status")
					.with(adminAuthentication())
					.with(csrf())
					.contentType(MediaType.APPLICATION_JSON)
					.content("{\"status\":\"SEARCHING\",\"reason\":\"Begin search\"}"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.status").value("SEARCHING"));

		verify(commandService).updateStatus(eq(101L), eq(request), eq(ADMIN_ID));
	}

	@Test
	void statusUpdateReturnsBusinessRuleError() throws Exception {
		CaseStatusUpdateRequest request = new CaseStatusUpdateRequest(CaseStatus.SEARCHING, "Begin search");
		org.mockito.Mockito.when(commandService.updateStatus(eq(101L), eq(request), eq(ADMIN_ID)))
				.thenThrow(new ApiException(
						HttpStatus.UNPROCESSABLE_ENTITY,
						"BUSINESS_RULE_VIOLATION",
						"Search prerequisites are missing"));

		mockMvc.perform(patch("/api/v1/admin/cases/101/status")
					.with(adminAuthentication())
					.with(csrf())
					.contentType(MediaType.APPLICATION_JSON)
					.content("{\"status\":\"SEARCHING\",\"reason\":\"Begin search\"}"))
				.andExpect(status().isUnprocessableEntity())
				.andExpect(jsonPath("$.code").value("BUSINESS_RULE_VIOLATION"));
	}

	@Test
	void closeReturnsClosedState() throws Exception {
		CaseCloseRequest request = new CaseCloseRequest("Search completed", false);
		org.mockito.Mockito.when(commandService.close(eq(101L), eq(request), eq(ADMIN_ID)))
				.thenReturn(new CaseStateResponse(101L, CaseStatus.CLOSED,
						Instant.parse("2026-07-20T03:00:00Z"),
						Instant.parse("2026-07-20T03:00:00Z")));

		mockMvc.perform(post("/api/v1/admin/cases/101/close")
					.with(adminAuthentication())
					.with(csrf())
					.contentType(MediaType.APPLICATION_JSON)
					.content("{\"reason\":\"Search completed\",\"force\":false}"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.status").value("CLOSED"));

		verify(commandService).close(eq(101L), eq(request), eq(ADMIN_ID));
	}

	@Test
	void closeReturnsConflictWhenPendingWorkExists() throws Exception {
		CaseCloseRequest request = new CaseCloseRequest("Search completed", false);
		org.mockito.Mockito.when(commandService.close(eq(101L), eq(request), eq(ADMIN_ID)))
				.thenThrow(new ApiException(
						HttpStatus.CONFLICT,
						"CASE_CLOSE_CONFLICT",
						"Pending work exists"));

		mockMvc.perform(post("/api/v1/admin/cases/101/close")
					.with(adminAuthentication())
					.with(csrf())
					.contentType(MediaType.APPLICATION_JSON)
					.content("{\"reason\":\"Search completed\",\"force\":false}"))
				.andExpect(status().isConflict())
				.andExpect(jsonPath("$.code").value("CASE_CLOSE_CONFLICT"));
	}

	@Test
	void caseWriteRequiresCsrf() throws Exception {
		mockMvc.perform(patch("/api/v1/admin/cases/101")
					.with(adminAuthentication())
					.contentType(MediaType.APPLICATION_JSON)
					.content("{\"missingName\":\"Updated Missing\"}"))
				.andExpect(status().isForbidden())
				.andExpect(jsonPath("$.code").value("ACCESS_DENIED"));
	}

	private RequestPostProcessor adminAuthentication() {
		AdminPrincipal principal = new AdminPrincipal(ADMIN_ID, "admin");
		return authentication(new UsernamePasswordAuthenticationToken(
				principal, null, principal.getAuthorities()));
	}

	private CaseDetailResponse caseDetail() {
		return new CaseDetailResponse(
				101L,
				CASE_NUMBER,
				CaseStatus.SEARCHING,
				new ReporterResponse(11L, "Reporter", "01012345678", "reporter@example.com", "Parent"),
				"Missing person report",
				"Missing",
				Gender.UNKNOWN,
				2000,
				new AppearanceResponse(null, null, "Coat", null, null, null, null, "Hat"),
				null,
				Instant.parse("2026-07-20T00:00:00Z"),
				null,
				null,
				"Seoul",
				Instant.parse("2026-07-20T01:00:00Z"),
				null,
				Instant.parse("2026-07-20T02:00:00Z"));
	}
}
