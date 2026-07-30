package com.ssafy.eyesonu;

import static org.hamcrest.Matchers.containsInAnyOrder;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.redirectedUrl;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.ssafy.eyesonu.admin.mapper.AdminMapper;
import com.ssafy.eyesonu.audit.mapper.AuditLogMapper;
import com.ssafy.eyesonu.common.config.SwaggerConfig;
import com.ssafy.eyesonu.missingcase.mapper.CaseStatusInquiryMapper;
import com.ssafy.eyesonu.missingcase.mapper.MissingCaseMapper;
import com.ssafy.eyesonu.mediaserver.mapper.MediaServerMapper;
import com.ssafy.eyesonu.camera.mapper.CameraMapper;
import com.ssafy.eyesonu.recording.mapper.RecordingMapper;
import com.ssafy.eyesonu.missingcase.service.CaseCommandService;
import com.ssafy.eyesonu.missingcase.service.CasePhotoService;
import com.ssafy.eyesonu.missingcase.service.CaseQueryService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

@ActiveProfiles("test")
@SpringBootTest(
		useMainMethod = SpringBootTest.UseMainMethod.ALWAYS,
		properties = {
				"springdoc.api-docs.enabled=true",
				"springdoc.swagger-ui.enabled=true"
		})
@Import(TestDatabaseConfiguration.class)
@AutoConfigureMockMvc
class SwaggerDocumentationTests {

	@Autowired
	private MockMvc mockMvc;

	@MockitoBean
	private AdminMapper adminMapper;

	@MockitoBean
	private AuditLogMapper auditLogMapper;

	@MockitoBean
	private CaseStatusInquiryMapper caseStatusInquiryMapper;

	@MockitoBean
	private MissingCaseMapper missingCaseMapper;

	@MockitoBean
	private MediaServerMapper mediaServerMapper;

	@MockitoBean
	private CameraMapper cameraMapper;

	@MockitoBean
	private RecordingMapper recordingMapper;

	@MockitoBean
	private CaseCommandService caseCommandService;

	@MockitoBean
	private CaseQueryService caseQueryService;

	@MockitoBean
	private CasePhotoService casePhotoService;

	@Test
	void apiDocsExposeImplementedControllersAndFilterLogoutOnly() throws Exception {
		mockMvc.perform(get("/v3/api-docs"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.info.title").value("EyesOnU API"))
				.andExpect(jsonPath("$.info.version").value("v1"))
				.andExpect(jsonPath("$.paths['/api/v1/auth/csrf'].get").exists())
				.andExpect(jsonPath("$.paths['/api/v1/auth/admin/login'].post").exists())
				.andExpect(jsonPath("$.paths['/api/v1/admins/me'].get").exists())
				.andExpect(jsonPath("$.paths['/api/v1/admins/me'].patch").exists())
				.andExpect(jsonPath("$.paths['/api/v1/cases/status-inquiries'].post").exists())
				.andExpect(jsonPath("$.paths['/api/v1/cases'].post").doesNotExist())
				.andExpect(jsonPath("$.paths['/api/v1/admin/cases'].post").exists())
				.andExpect(jsonPath("$.paths['/api/v1/admin/cases'].get").exists())
				.andExpect(jsonPath("$.paths['/api/v1/admin/cases/{caseId}'].get").exists())
				.andExpect(jsonPath("$.paths['/api/v1/admin/cases/{caseId}'].patch").exists())
				.andExpect(jsonPath("$.paths['/api/v1/admin/cases/{caseId}/photo'].put").exists())
				.andExpect(jsonPath("$.paths['/api/v1/admin/cases/{caseId}/photo'].delete").exists())
				.andExpect(jsonPath("$.paths['/api/v1/admin/cases/{caseId}/status'].patch").exists())
				.andExpect(jsonPath("$.paths['/api/v1/admin/cases/{caseId}/close'].post").exists())
				.andExpect(jsonPath("$.paths['/api/v1/auth/admin/logout'].post").exists())
				.andExpect(jsonPath(
						"$.paths['/api/v1/device/cameras/{cameraCode}/recordings'].post").exists())
				.andExpect(jsonPath("$.paths['/api/v1/admin/recordings'].get").exists())
				.andExpect(jsonPath("$.paths['/api/v1/admin/recordings/{recordingId}'].get").exists())
				.andExpect(jsonPath("$.paths['/api/v1/admin/cameras'].get").exists())
				.andExpect(jsonPath("$.paths['/api/v1/admin/cameras'].post").exists())
				.andExpect(jsonPath("$.paths['/api/v1/admin/cameras/{cameraId}'].get").exists())
				.andExpect(jsonPath("$.paths['/api/v1/admin/cameras/{cameraId}/name'].patch").exists())
				.andExpect(jsonPath("$.paths['/api/v1/admin/cameras/{cameraId}'].put").exists())
				.andExpect(jsonPath("$.paths['/api/v1/admin/cameras/{cameraId}'].patch").doesNotExist())
				.andExpect(jsonPath("$.paths['/api/v1/admin/cameras'].get.summary")
						.value("카메라 목록 조회"))
				.andExpect(jsonPath("$.paths['/api/v1/admin/cameras'].post.summary")
						.value("카메라 등록"))
				.andExpect(jsonPath("$.paths['/api/v1/admin/cameras/{cameraId}'].get.summary")
						.value("카메라 상세 조회"))
				.andExpect(jsonPath("$.paths['/api/v1/admin/cameras/{cameraId}/name'].patch.summary")
						.value("카메라 이름 수정"))
				.andExpect(jsonPath("$.paths['/api/v1/admin/cameras/{cameraId}'].put.summary")
						.value("카메라 정보·소속 전체 수정"))
				.andExpect(jsonPath(
						"$.paths['/api/v1/device/cameras/{cameraCode}/recordings'].patch").doesNotExist())
				.andExpect(jsonPath(
						"$.paths['/api/v1/device/recordings/{recordingId}/upload-status']").doesNotExist())
				.andExpect(jsonPath("$.components.schemas.ApiErrorResponse").exists())
				.andExpect(jsonPath(
						"$.paths['/api/v1/auth/admin/login'].post.responses['200']"
								+ ".content['application/json'].schema['$ref']").exists())
				.andExpect(jsonPath(
						"$.paths['/api/v1/admins/me'].get.responses['200']"
								+ ".content['application/json'].schema['$ref']").exists())
				.andExpect(jsonPath(
						"$.paths['/api/v1/admins/me'].patch.responses['200']"
								+ ".content['application/json'].schema['$ref']").exists())
				.andExpect(jsonPath(
						"$.paths['/api/v1/cases/status-inquiries'].post.responses['200']"
								+ ".content['application/json'].schema['$ref']").exists())
				.andExpect(jsonPath("$.paths['/api/v1/auth/csrf'].get.responses['204'].content")
						.doesNotExist());
	}

	@Test
	void apiDocsDescribeSecurityAndFilterResponses() throws Exception {
		mockMvc.perform(get("/v3/api-docs"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.components.securitySchemes.%s.name"
						.formatted(SwaggerConfig.SESSION_SCHEME)).value("EYESONU_SESSION"))
				.andExpect(jsonPath("$.components.securitySchemes.%s.name"
						.formatted(SwaggerConfig.CSRF_SCHEME)).value("X-XSRF-TOKEN"))
				.andExpect(jsonPath("$.components.securitySchemes.%s.name"
						.formatted(SwaggerConfig.DEVICE_KEY_SCHEME)).value("X-Device-Key"))
				.andExpect(jsonPath("$.components.securitySchemes.%s.in"
						.formatted(SwaggerConfig.DEVICE_KEY_SCHEME)).value("header"))
				.andExpect(jsonPath("$.paths['/api/v1/auth/admin/login'].post.security[0].%s"
						.formatted(SwaggerConfig.CSRF_SCHEME)).isArray())
				.andExpect(jsonPath("$.paths['/api/v1/admins/me'].get.security[0].%s"
						.formatted(SwaggerConfig.SESSION_SCHEME)).isArray())
				.andExpect(jsonPath("$.paths['/api/v1/admins/me'].patch.security[0].%s"
						.formatted(SwaggerConfig.SESSION_SCHEME)).isArray())
				.andExpect(jsonPath("$.paths['/api/v1/admins/me'].patch.security[0].%s"
						.formatted(SwaggerConfig.CSRF_SCHEME)).isArray())
				.andExpect(jsonPath("$.paths['/api/v1/admins/me'].patch.security.length()")
						.value(1))
				.andExpect(jsonPath("$.paths['/api/v1/auth/admin/logout'].post.security[0].%s"
						.formatted(SwaggerConfig.CSRF_SCHEME)).isArray())
				.andExpect(jsonPath("$.paths['/api/v1/auth/admin/logout'].post.responses['204']").exists())
				.andExpect(jsonPath("$.paths['/api/v1/auth/admin/logout'].post.responses['403']").exists())
				.andExpect(jsonPath("$.paths['/api/v1/auth/admin/logout'].post.responses['401']").doesNotExist())
				.andExpect(jsonPath(
						"$.paths['/api/v1/auth/admin/logout'].post.responses['403']"
								+ ".content['application/json'].schema['$ref']")
						.value("#/components/schemas/ApiErrorResponse"))
				.andExpect(jsonPath(
						"$.paths['/api/v1/device/cameras/{cameraCode}/recordings'].post.security[0].%s"
								.formatted(SwaggerConfig.DEVICE_KEY_SCHEME)).isArray())
				.andExpect(jsonPath(
						"$.paths['/api/v1/device/cameras/{cameraCode}/recordings'].post"
								+ ".parameters[1].name")
						.value("Idempotency-Key"))
				.andExpect(jsonPath(
						"$.paths['/api/v1/device/cameras/{cameraCode}/recordings'].post"
								+ ".parameters[1].in")
						.value("header"))
				.andExpect(jsonPath(
						"$.paths['/api/v1/device/cameras/{cameraCode}/recordings'].post"
								+ ".parameters[1].required")
						.value(true))
				.andExpect(jsonPath(
						"$.paths['/api/v1/device/cameras/{cameraCode}/recordings'].post.responses['200']")
						.exists())
				.andExpect(jsonPath(
						"$.paths['/api/v1/device/cameras/{cameraCode}/recordings'].post.responses['201']")
						.exists())
				.andExpect(jsonPath(
						"$.paths['/api/v1/device/cameras/{cameraCode}/recordings'].post.responses['400']")
						.exists())
				.andExpect(jsonPath(
						"$.paths['/api/v1/device/cameras/{cameraCode}/recordings'].post.responses['401']")
						.exists())
				.andExpect(jsonPath(
						"$.paths['/api/v1/device/cameras/{cameraCode}/recordings'].post.responses['403']")
						.exists())
				.andExpect(jsonPath(
						"$.paths['/api/v1/device/cameras/{cameraCode}/recordings'].post.responses['404']")
						.exists())
				.andExpect(jsonPath(
						"$.paths['/api/v1/device/cameras/{cameraCode}/recordings'].post.responses['409']")
						.exists())
				.andExpect(jsonPath(
						"$.paths['/api/v1/device/cameras/{cameraCode}/recordings'].post.responses['413']")
						.exists())
				.andExpect(jsonPath(
						"$.paths['/api/v1/device/cameras/{cameraCode}/recordings'].post.responses['415']")
						.exists())
				.andExpect(jsonPath(
						"$.paths['/api/v1/device/cameras/{cameraCode}/recordings'].post.responses['422']")
						.exists())
				.andExpect(jsonPath(
						"$.paths['/api/v1/device/cameras/{cameraCode}/recordings'].post.responses['503']")
						.exists())
				.andExpect(jsonPath(
						"$.paths['/api/v1/device/cameras/{cameraCode}/recordings'].post.responses['429']")
						.doesNotExist());
	}

	@Test
	void recordingSchemasMatchThePublishedContract() throws Exception {
		mockMvc.perform(get("/v3/api-docs"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.components.schemas.RecordingCreateRequest.properties.startTime")
						.exists())
				.andExpect(jsonPath("$.components.schemas.RecordingCreateRequest.properties.endTime")
						.exists())
				.andExpect(jsonPath("$.components.schemas.RecordingCreateRequest.properties.objectKey")
						.exists())
				.andExpect(jsonPath("$.components.schemas.RecordingCreateRequest.properties.fileSize")
						.doesNotExist())
				.andExpect(jsonPath("$.components.schemas.RecordingCreateRequest.properties.uploadStatus")
						.doesNotExist())
				.andExpect(jsonPath("$.components.schemas.RecordingCreateResponse.properties.duplicate")
						.exists())
				.andExpect(jsonPath("$.components.schemas.AdminRecordingListResponse.properties.videoUrl")
						.doesNotExist())
				.andExpect(jsonPath("$.components.schemas.AdminRecordingDetailResponse.properties.videoUrl")
						.exists())
				.andExpect(jsonPath("$.components.schemas.AdminRecordingListResponse.properties.objectKey")
						.doesNotExist())
				.andExpect(jsonPath("$.components.schemas.AdminRecordingDetailResponse.properties.s3Key")
						.doesNotExist())
				.andExpect(jsonPath("$.components.schemas.PageMeta.properties.totalElements").exists())
				.andExpect(jsonPath("$.components.schemas.PageMeta.properties.totalPages").exists());
	}

	@Test
	void caseStatusInquirySchemaPublishesEveryCaseStatus() throws Exception {
		mockMvc.perform(get("/v3/api-docs"))
				.andExpect(status().isOk())
				.andExpect(jsonPath(
						"$.components.schemas.CaseStatusInquiryResponse.properties.status.enum",
						containsInAnyOrder(
								"RECEIVED",
								"SEARCHING",
								"CANDIDATE_FOUND",
								"FIELD_SEARCH",
								"CLOSED")));
	}

	@Test
	void swaggerUiIsReachableWithoutAuthentication() throws Exception {
		mockMvc.perform(get("/swagger-ui.html"))
				.andExpect(status().is3xxRedirection())
				.andExpect(redirectedUrl("/swagger-ui/index.html"));
	}
}
