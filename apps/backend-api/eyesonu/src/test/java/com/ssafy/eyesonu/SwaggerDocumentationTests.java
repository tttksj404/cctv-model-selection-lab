package com.ssafy.eyesonu;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.redirectedUrl;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.ssafy.eyesonu.admin.mapper.AdminMapper;
import com.ssafy.eyesonu.audit.mapper.AuditLogMapper;
import com.ssafy.eyesonu.caseinquiry.mapper.CaseInquiryMapper;
import com.ssafy.eyesonu.common.config.SwaggerConfig;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

@ActiveProfiles("test")
@SpringBootTest(
		useMainMethod = SpringBootTest.UseMainMethod.ALWAYS,
		properties = {
				"springdoc.api-docs.enabled=true",
				"springdoc.swagger-ui.enabled=true"
		})
@AutoConfigureMockMvc
class SwaggerDocumentationTests {

	@Autowired
	private MockMvc mockMvc;

	@MockitoBean
	private AdminMapper adminMapper;

	@MockitoBean
	private AuditLogMapper auditLogMapper;

	@MockitoBean
	private CaseInquiryMapper caseInquiryMapper;

	@Test
	void apiDocsExposeImplementedControllersAndFilterLogoutOnly() throws Exception {
		MvcResult result = mockMvc.perform(get("/v3/api-docs"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.info.title").value("EyesOnU API"))
				.andExpect(jsonPath("$.info.version").value("v1"))
				.andExpect(jsonPath("$.paths['/api/v1/auth/csrf'].get").exists())
				.andExpect(jsonPath("$.paths['/api/v1/auth/admin/login'].post").exists())
				.andExpect(jsonPath("$.paths['/api/v1/admins/me'].get").exists())
				.andExpect(jsonPath("$.paths['/api/v1/admins/me'].patch").exists())
				.andExpect(jsonPath("$.paths['/api/v1/cases/status-inquiries'].post").exists())
				.andExpect(jsonPath("$.paths['/api/v1/auth/admin/logout'].post").exists())
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
						.doesNotExist())
				.andReturn();

		assertFalse(result.getResponse().getContentAsString().contains("\"/api/v1/device/"));
	}

	@Test
	void apiDocsDescribeSecurityAndFilterResponses() throws Exception {
		mockMvc.perform(get("/v3/api-docs"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.components.securitySchemes.%s.name"
						.formatted(SwaggerConfig.SESSION_SCHEME)).value("EYESONU_SESSION"))
				.andExpect(jsonPath("$.components.securitySchemes.%s.name"
						.formatted(SwaggerConfig.CSRF_SCHEME)).value("X-XSRF-TOKEN"))
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
						.value("#/components/schemas/ApiErrorResponse"));
	}

	@Test
	void swaggerUiIsReachableWithoutAuthentication() throws Exception {
		mockMvc.perform(get("/swagger-ui.html"))
				.andExpect(status().is3xxRedirection())
				.andExpect(redirectedUrl("/swagger-ui/index.html"));
	}
}
