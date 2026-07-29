package com.ssafy.eyesonu;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.when;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.authentication;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.csrf;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.cookie;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.ssafy.eyesonu.admin.domain.Admin;
import com.ssafy.eyesonu.admin.mapper.AdminMapper;
import com.ssafy.eyesonu.audit.mapper.AuditLogMapper;
import com.ssafy.eyesonu.auth.security.AdminPrincipal;
import com.ssafy.eyesonu.missingcase.domain.CaseStatus;
import com.ssafy.eyesonu.missingcase.domain.CaseStatusInquiryRow;
import com.ssafy.eyesonu.missingcase.mapper.CaseStatusInquiryMapper;
import com.ssafy.eyesonu.missingcase.mapper.MissingCaseMapper;
import com.ssafy.eyesonu.mediaserver.mapper.MediaServerMapper;
import com.ssafy.eyesonu.camera.mapper.CameraMapper;
import com.ssafy.eyesonu.recording.mapper.RecordingMapper;
import com.ssafy.eyesonu.missingcase.service.CaseCommandService;
import com.ssafy.eyesonu.missingcase.service.CasePhotoService;
import com.ssafy.eyesonu.missingcase.service.CaseQueryService;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseCreateResponse;
import com.ssafy.eyesonu.recording.service.RecordingQueryService;
import jakarta.servlet.http.Cookie;
import java.time.Instant;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.http.MediaType;
import org.springframework.dao.DataAccessResourceFailureException;
import org.springframework.context.annotation.Import;
import org.springframework.mock.web.MockHttpSession;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

@ActiveProfiles("test")
@SpringBootTest(useMainMethod = SpringBootTest.UseMainMethod.ALWAYS)
@Import(TestDatabaseConfiguration.class)
@AutoConfigureMockMvc
class AuthAndInquiryApiTests {

	@Autowired
	private MockMvc mockMvc;

	@Autowired
	private PasswordEncoder passwordEncoder;

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
	private RecordingQueryService recordingQueryService;

	@MockitoBean
	private CaseCommandService caseCommandService;

	@MockitoBean
	private CaseQueryService caseQueryService;

	@MockitoBean
	private CasePhotoService casePhotoService;

	private Admin admin;

	@BeforeEach
	void setUp() {
		admin = new Admin(1L, "admin", passwordEncoder.encode("correct-password!"), "Administrator");
		when(adminMapper.findByLoginId("admin")).thenReturn(Optional.of(admin));
		when(adminMapper.findById(1L)).thenReturn(Optional.of(admin));
	}

	@Test
	void csrfEndpointIssuesReadableTokenCookieWithoutResponseBody() throws Exception {
		mockMvc.perform(get("/api/v1/auth/csrf"))
				.andExpect(status().isNoContent())
				.andExpect(cookie().exists("XSRF-TOKEN"))
				.andExpect(header().string("Cache-Control", "no-store"));
	}

	@Test
	void loginRequiresCsrfAndCreatesAuthenticatedSessionWithoutJwt() throws Exception {
		String body = """
				{"loginId":"admin","password":"correct-password!"}
				""";
		mockMvc.perform(post("/api/v1/auth/admin/login")
						.contentType(MediaType.APPLICATION_JSON)
						.content(body))
				.andExpect(status().isForbidden());

		MvcResult csrfResult = mockMvc.perform(get("/api/v1/auth/csrf"))
				.andExpect(status().isNoContent())
				.andReturn();
		Cookie csrfCookie = csrfResult.getResponse().getCookie("XSRF-TOKEN");

		MvcResult login = mockMvc.perform(post("/api/v1/auth/admin/login")
						.cookie(csrfCookie)
						.header("X-XSRF-TOKEN", csrfCookie.getValue())
						.contentType(MediaType.APPLICATION_JSON)
						.content(body))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.id").value(1))
				.andExpect(jsonPath("$.data.accessToken").doesNotExist())
				.andReturn();

		MockHttpSession session = (MockHttpSession) login.getRequest().getSession(false);
		mockMvc.perform(get("/api/v1/admins/me").session(session))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.loginId").value("admin"));
	}

	@Test
	void unauthenticatedAdminRequestReturnsJson401() throws Exception {
		mockMvc.perform(get("/api/v1/admins/me"))
				.andExpect(status().isUnauthorized())
				.andExpect(jsonPath("$.code").value("AUTHENTICATION_REQUIRED"));
	}

	@Test
	void secondLoginExpiresTheFirstSession() throws Exception {
		MvcResult firstLogin = login();
		MvcResult secondLogin = login();
		MockHttpSession firstSession = (MockHttpSession) firstLogin.getRequest().getSession(false);
		MockHttpSession secondSession = (MockHttpSession) secondLogin.getRequest().getSession(false);

		mockMvc.perform(get("/api/v1/admins/me").session(firstSession))
				.andExpect(status().isUnauthorized())
				.andExpect(jsonPath("$.code").value("SESSION_EXPIRED"));
		mockMvc.perform(get("/api/v1/admins/me").session(secondSession))
				.andExpect(status().isOk());
	}

	@Test
	void logoutRequiresCsrfAndInvalidatesTheSession() throws Exception {
		MvcResult login = login();
		MockHttpSession session = (MockHttpSession) login.getRequest().getSession(false);

		mockMvc.perform(post("/api/v1/auth/admin/logout").session(session))
				.andExpect(status().isForbidden());

		MvcResult csrfResult = mockMvc.perform(get("/api/v1/auth/csrf").session(session)).andReturn();
		Cookie csrfCookie = csrfResult.getResponse().getCookie("XSRF-TOKEN");
		mockMvc.perform(post("/api/v1/auth/admin/logout")
						.session(session)
						.cookie(csrfCookie)
						.header("X-XSRF-TOKEN", csrfCookie.getValue()))
				.andExpect(status().isNoContent());

		assertTrue(session.isInvalid());
	}

	@Test
	void inquiryReturnsOnlyMinimalFieldsAndNoStore() throws Exception {
		when(caseStatusInquiryMapper.findStatus(any(), any())).thenReturn(Optional.of(new CaseStatusInquiryRow(
				2L,
				"EFU-0123456789ABCDEFGHJKMNPQRS",
				CaseStatus.SEARCHING,
				Instant.parse("2026-07-20T01:30:00Z"),
				Instant.parse("2026-07-20T02:20:00Z"),
				null)));

		mockMvc.perform(post("/api/v1/cases/status-inquiries")
						.contentType(MediaType.APPLICATION_JSON)
						.content("""
								{"caseNumber":"efu-0123456789abcdefghjkmnpqrs","phone":"010-1234-5678"}
								"""))
				.andExpect(status().isOk())
				.andExpect(header().string("Cache-Control", "no-store"))
				.andExpect(jsonPath("$.data.status").value("SEARCHING"))
				.andExpect(jsonPath("$.data.reportedAt").value("2026-07-20T01:30:00Z"))
				.andExpect(jsonPath("$.data.updatedAt").value("2026-07-20T02:20:00Z"))
				.andExpect(jsonPath("$.data.missingName").doesNotExist())
				.andExpect(jsonPath("$.data.photoUrl").doesNotExist())
				.andExpect(jsonPath("$.data.confirmedSightings").doesNotExist());

		verify(caseStatusInquiryMapper).findStatus(
				"EFU-0123456789ABCDEFGHJKMNPQRS", "01012345678");
	}

	@Test
	void inquiryMismatchUsesGeneric404AndNoStore() throws Exception {
		when(caseStatusInquiryMapper.findStatus(any(), any())).thenReturn(Optional.empty());
		mockMvc.perform(post("/api/v1/cases/status-inquiries")
						.contentType(MediaType.APPLICATION_JSON)
						.content("""
								{"caseNumber":"EFU-0123456789ABCDEFGHJKMNPQRS","phone":"01012345678"}
								"""))
				.andExpect(status().isNotFound())
				.andExpect(header().string("Cache-Control", "no-store"))
				.andExpect(jsonPath("$.code").value("INQUIRY_NOT_FOUND"));
	}

	@Test
	void inquiryDoesNotReturnDataWhenRequiredAuditWriteFails() throws Exception {
		when(caseStatusInquiryMapper.findStatus(any(), any())).thenReturn(Optional.of(new CaseStatusInquiryRow(
				2L,
				"EFU-0123456789ABCDEFGHJKMNPQRS",
				CaseStatus.SEARCHING,
				Instant.parse("2026-07-20T01:30:00Z"),
				Instant.parse("2026-07-20T02:20:00Z"),
				null)));
		doThrow(new DataAccessResourceFailureException("audit unavailable"))
				.when(auditLogMapper)
				.insert(any(), any(), any(), any(), any(), any());

		mockMvc.perform(post("/api/v1/cases/status-inquiries")
						.contentType(MediaType.APPLICATION_JSON)
						.content("""
								{"caseNumber":"EFU-0123456789ABCDEFGHJKMNPQRS","phone":"01012345678"}
								"""))
				.andExpect(status().isServiceUnavailable())
				.andExpect(header().string("Cache-Control", "no-store"))
				.andExpect(jsonPath("$.code").value("DATABASE_UNAVAILABLE"))
				.andExpect(jsonPath("$.data").doesNotExist());
	}

	@Test
	void inquiryRejectsLettersAndParenthesesInPhoneNumber() throws Exception {
		mockMvc.perform(post("/api/v1/cases/status-inquiries")
					.contentType(MediaType.APPLICATION_JSON)
					.content("""
							{"caseNumber":"EFU-0123456789ABCDEFGHJKMNPQRS","phone":"abc010-1234-5678"}
							"""))
				.andExpect(status().isBadRequest())
				.andExpect(header().string("Cache-Control", "no-store"))
				.andExpect(jsonPath("$.code").value("VALIDATION_ERROR"));

		mockMvc.perform(post("/api/v1/cases/status-inquiries")
					.contentType(MediaType.APPLICATION_JSON)
					.content("""
							{"caseNumber":"EFU-0123456789ABCDEFGHJKMNPQRS","phone":"010 (1234) 5678"}
							"""))
				.andExpect(status().isBadRequest())
				.andExpect(header().string("Cache-Control", "no-store"))
				.andExpect(jsonPath("$.code").value("VALIDATION_ERROR"));
	}

	@Test
	void invalidAdminRecordingQueryTypeReturnsStructuredValidationError() throws Exception {
		MockHttpSession session = (MockHttpSession) login().getRequest().getSession(false);

		mockMvc.perform(get("/api/v1/admin/recordings")
					.session(session)
					.param("page", "not-an-integer"))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("VALIDATION_ERROR"));
	}

	@Test
	void adminCaseCreationRequiresAuthenticationAndCsrfAndPublicCreationIsBlocked() throws Exception {
		String body = """
				{
				  "reporter":{"name":"홍길동","phone":"010-1234-5678"},
				  "reportContent":"실종 경위",
				  "missingName":"김민수",
				  "gender":"MALE",
				  "appearance":{"upperClothing":"검은 셔츠"},
				  "lastSeenTime":"2026-07-20T00:10:00+09:00",
				  "lastSeenAddress":"서울 강남구"
				}
				""";

		mockMvc.perform(get("/api/v1/admin/cases"))
				.andExpect(status().isUnauthorized());
		mockMvc.perform(post("/api/v1/cases").contentType(MediaType.APPLICATION_JSON).content(body))
				.andExpect(status().isForbidden());

		AdminPrincipal principal = new AdminPrincipal(1L, "admin");
		UsernamePasswordAuthenticationToken authentication = new UsernamePasswordAuthenticationToken(
				principal, null, principal.getAuthorities());
		mockMvc.perform(post("/api/v1/admin/cases")
					.with(authentication(authentication))
					.contentType(MediaType.APPLICATION_JSON)
					.content(body))
				.andExpect(status().isForbidden());

		when(caseCommandService.create(any(), any())).thenReturn(new CaseCreateResponse(
				101L, "EFU-0123456789ABCDEFGHJKMNPQRS", CaseStatus.RECEIVED,
				Instant.parse("2026-07-20T01:30:00Z")));
		mockMvc.perform(post("/api/v1/admin/cases")
					.with(authentication(authentication))
					.with(csrf())
					.contentType(MediaType.APPLICATION_JSON)
					.content(body))
				.andExpect(status().isCreated())
				.andExpect(header().string("Location", "/api/v1/admin/cases/101"));
	}

	private MvcResult login() throws Exception {
		MvcResult csrfResult = mockMvc.perform(get("/api/v1/auth/csrf")).andReturn();
		Cookie csrfCookie = csrfResult.getResponse().getCookie("XSRF-TOKEN");
		return mockMvc.perform(post("/api/v1/auth/admin/login")
						.cookie(csrfCookie)
						.header("X-XSRF-TOKEN", csrfCookie.getValue())
						.contentType(MediaType.APPLICATION_JSON)
						.content("""
								{"loginId":"admin","password":"correct-password!"}
								"""))
				.andExpect(status().isOk())
				.andReturn();
	}
}
