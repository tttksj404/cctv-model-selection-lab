package com.ssafy.eyesonu.common.config;

import com.ssafy.eyesonu.auth.device.DeviceKeyAuthenticationFilter;
import com.ssafy.eyesonu.common.api.ApiErrorResponse;
import io.swagger.v3.core.converter.ModelConverters;
import io.swagger.v3.oas.models.Components;
import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.Operation;
import io.swagger.v3.oas.models.PathItem;
import io.swagger.v3.oas.models.Paths;
import io.swagger.v3.oas.models.info.Info;
import io.swagger.v3.oas.models.media.Content;
import io.swagger.v3.oas.models.media.Schema;
import io.swagger.v3.oas.models.responses.ApiResponses;
import io.swagger.v3.oas.models.security.SecurityRequirement;
import io.swagger.v3.oas.models.security.SecurityScheme;
import io.swagger.v3.oas.models.tags.Tag;
import java.util.List;
import org.springdoc.core.customizers.OpenApiCustomizer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class SwaggerConfig {

	public static final String SESSION_SCHEME = "sessionCookie";
	public static final String CSRF_SCHEME = "csrfToken";
	public static final String DEVICE_KEY_SCHEME = "deviceKey";

	private static final String ADMIN_ME_PATH = "/api/v1/admins/me";
	private static final String LOGOUT_PATH = "/api/v1/auth/admin/logout";
	private static final String ERROR_SCHEMA_REF = "#/components/schemas/ApiErrorResponse";

	@Bean
	OpenAPI eyesOnUOpenAPI() {
		Components components = new Components()
				.addSecuritySchemes(SESSION_SCHEME, new SecurityScheme()
						.type(SecurityScheme.Type.APIKEY)
						.in(SecurityScheme.In.COOKIE)
						.name("EYESONU_SESSION")
						.description("관리자 로그인으로 발급되는 서버 세션 쿠키"))
				.addSecuritySchemes(CSRF_SCHEME, new SecurityScheme()
						.type(SecurityScheme.Type.APIKEY)
						.in(SecurityScheme.In.HEADER)
						.name("X-XSRF-TOKEN")
						.description("GET /api/v1/auth/csrf가 발급한 XSRF-TOKEN 쿠키와 동일한 값"))
				.addSecuritySchemes(DEVICE_KEY_SCHEME, new SecurityScheme()
						.type(SecurityScheme.Type.APIKEY)
						.in(SecurityScheme.In.HEADER)
						.name(DeviceKeyAuthenticationFilter.HEADER_NAME)
						.description("미디어 서버에 발급된 Device Key"));
		ModelConverters.getInstance().read(ApiErrorResponse.class)
				.forEach(components::addSchemas);

		return new OpenAPI()
				.info(new Info()
						.title("EyesOnU API")
						.version("v1")
						.description("""
								EyesOnU REST API 문서입니다.

								관리자 API 호출 순서:
								1. CSRF 토큰 발급 API를 호출합니다.
								2. XSRF-TOKEN 쿠키 값을 X-XSRF-TOKEN 인증 값으로 입력합니다.
								3. 관리자 로그인 API를 호출한 뒤 관리자 API를 사용합니다.
								"""))
				.components(components)
				.tags(List.of(
						new Tag().name("인증").description("관리자 세션 인증과 CSRF 토큰 API"),
						new Tag().name("관리자").description("로그인한 관리자 정보 API"),
						new Tag().name("관리자 사건").description("관리자 전용 사건 등록·조회·수정·상태 관리 API"),
						new Tag().name("사건 조회").description("신고자의 사건 진행 상황 조회 API")));
	}

	@Bean
	OpenApiCustomizer securityFilterEndpointCustomizer() {
		return openApi -> {
			combineAdminUpdateSecurity(openApi);
			addLogoutPath(openApi);
			normalizeJsonResponseMediaTypes(openApi);
		};
	}

	private void combineAdminUpdateSecurity(OpenAPI openApi) {
		PathItem adminMe = openApi.getPaths() == null ? null : openApi.getPaths().get(ADMIN_ME_PATH);
		if (adminMe != null && adminMe.getPatch() != null) {
			adminMe.getPatch().setSecurity(List.of(new SecurityRequirement()
					.addList(SESSION_SCHEME)
					.addList(CSRF_SCHEME)));
		}
	}

	private void addLogoutPath(OpenAPI openApi) {
		if (openApi.getPaths() == null) {
			openApi.setPaths(new Paths());
		}
		PathItem logoutPath = openApi.getPaths().get(LOGOUT_PATH);
		if (logoutPath != null && logoutPath.getPost() != null) {
			return;
		}

		Operation logout = new Operation()
				.operationId("adminLogout")
				.summary("관리자 로그아웃")
				.description("Spring Security 필터가 처리합니다. 기존 관리자 세션과 인증이 있다면 "
						+ "제거하고 세션 및 CSRF 쿠키를 만료시킵니다.")
				.tags(List.of("인증"))
				.security(List.of(new SecurityRequirement().addList(CSRF_SCHEME)))
				.responses(new ApiResponses()
						.addApiResponse("204", new io.swagger.v3.oas.models.responses.ApiResponse()
								.description("로그아웃 완료"))
						.addApiResponse("403", errorResponse("CSRF 토큰 누락 또는 불일치")));

		if (logoutPath == null) {
			openApi.path(LOGOUT_PATH, new PathItem().post(logout));
		}
		else {
			logoutPath.setPost(logout);
		}
	}

	private void normalizeJsonResponseMediaTypes(OpenAPI openApi) {
		if (openApi.getPaths() == null) {
			return;
		}
		openApi.getPaths().values().stream()
				.flatMap(pathItem -> pathItem.readOperations().stream())
				.flatMap(operation -> operation.getResponses().values().stream())
				.map(io.swagger.v3.oas.models.responses.ApiResponse::getContent)
				.filter(content -> content != null && content.containsKey("*/*"))
				.forEach(content -> {
					io.swagger.v3.oas.models.media.MediaType inferred = content.remove("*/*");
					io.swagger.v3.oas.models.media.MediaType json = content.get("application/json");
					if (json == null || json.getSchema() == null) {
						content.put("application/json", inferred);
					}
				});
	}

	private io.swagger.v3.oas.models.responses.ApiResponse errorResponse(String description) {
		return new io.swagger.v3.oas.models.responses.ApiResponse()
				.description(description)
				.content(new Content().addMediaType(
						"application/json",
						new io.swagger.v3.oas.models.media.MediaType()
								.schema(new Schema<>().$ref(ERROR_SCHEMA_REF))));
	}
}
