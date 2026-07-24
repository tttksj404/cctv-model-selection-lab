package com.ssafy.eyesonu;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.when;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.cookie;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.ssafy.eyesonu.admin.domain.Admin;
import com.ssafy.eyesonu.admin.mapper.AdminMapper;
import com.ssafy.eyesonu.audit.mapper.AuditLogMapper;
import com.ssafy.eyesonu.caseinquiry.mapper.CaseInquiryMapper;
import com.ssafy.eyesonu.caseinquiry.mapper.CaseInquiryMapper.CaseStatusRow;
import jakarta.servlet.http.Cookie;
import java.time.LocalDateTime;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.http.MediaType;
import org.springframework.dao.DataAccessResourceFailureException;
import org.springframework.mock.web.MockHttpSession;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

@ActiveProfiles("test")
@SpringBootTest(useMainMethod = SpringBootTest.UseMainMethod.ALWAYS)
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
	private CaseInquiryMapper caseInquiryMapper;

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
		when(caseInquiryMapper.findStatus(any(), any())).thenReturn(Optional.of(new CaseStatusRow(
				2L,
				"EFU-0123456789ABCDEFGHJKMNPQRS",
				"SEARCHING",
				LocalDateTime.of(2026, 7, 20, 1, 30),
				LocalDateTime.of(2026, 7, 20, 2, 20),
				null)));

		mockMvc.perform(post("/api/v1/cases/status-inquiries")
						.contentType(MediaType.APPLICATION_JSON)
						.content("""
								{"caseNumber":"efu-0123456789abcdefghjkmnpqrs","phone":"010-1234-5678"}
								"""))
				.andExpect(status().isOk())
				.andExpect(header().string("Cache-Control", "no-store"))
				.andExpect(jsonPath("$.data.status").value("SEARCHING"))
				.andExpect(jsonPath("$.data.missingName").doesNotExist())
				.andExpect(jsonPath("$.data.photoUrl").doesNotExist())
				.andExpect(jsonPath("$.data.confirmedSightings").doesNotExist());
	}

	@Test
	void inquiryMismatchUsesGeneric404AndNoStore() throws Exception {
		when(caseInquiryMapper.findStatus(any(), any())).thenReturn(Optional.empty());
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
		when(caseInquiryMapper.findStatus(any(), any())).thenReturn(Optional.of(new CaseStatusRow(
				2L,
				"EFU-0123456789ABCDEFGHJKMNPQRS",
				"SEARCHING",
				LocalDateTime.of(2026, 7, 20, 1, 30),
				LocalDateTime.of(2026, 7, 20, 2, 20),
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
