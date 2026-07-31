package com.ssafy.eyesonu.auth.controller;

import com.ssafy.eyesonu.admin.dto.AdminResponse;
import com.ssafy.eyesonu.admin.domain.Admin;
import com.ssafy.eyesonu.admin.mapper.AdminMapper;
import com.ssafy.eyesonu.audit.service.AuditService;
import com.ssafy.eyesonu.auth.ratelimit.AttemptRateLimiter;
import com.ssafy.eyesonu.auth.dto.AdminLoginRequest;
import com.ssafy.eyesonu.auth.controller.docs.AuthControllerDocs;
import com.ssafy.eyesonu.auth.security.AdminAuthenticationProvider;
import com.ssafy.eyesonu.auth.security.AdminPrincipal;
import com.ssafy.eyesonu.common.api.ApiResponse;
import com.ssafy.eyesonu.common.exception.ApiException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.validation.Valid;
import java.util.Map;
import org.springframework.http.CacheControl;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.AuthenticationException;
import org.springframework.security.core.context.SecurityContext;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.authentication.session.SessionAuthenticationStrategy;
import org.springframework.security.web.context.SecurityContextRepository;
import org.springframework.security.web.csrf.CsrfToken;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/auth")
public class AuthController implements AuthControllerDocs {

	private static final String RATE_LIMIT_SCOPE = "admin-login";

	private final AuthenticationManager authenticationManager;
	private final SessionAuthenticationStrategy sessionAuthenticationStrategy;
	private final SecurityContextRepository securityContextRepository;
	private final AdminMapper adminMapper;
	private final AttemptRateLimiter rateLimiter;
	private final AuditService auditService;

	public AuthController(
			AuthenticationManager authenticationManager,
			SessionAuthenticationStrategy sessionAuthenticationStrategy,
			SecurityContextRepository securityContextRepository,
			AdminMapper adminMapper,
			AttemptRateLimiter rateLimiter,
			AuditService auditService) {
		this.authenticationManager = authenticationManager;
		this.sessionAuthenticationStrategy = sessionAuthenticationStrategy;
		this.securityContextRepository = securityContextRepository;
		this.adminMapper = adminMapper;
		this.rateLimiter = rateLimiter;
		this.auditService = auditService;
	}

	@GetMapping("/csrf")
	@Override
	public ResponseEntity<Void> csrf(CsrfToken csrfToken) {
		csrfToken.getToken();
		return ResponseEntity.noContent().cacheControl(CacheControl.noStore()).build();
	}

	@PostMapping("/admin/login")
	@Override
	public ResponseEntity<ApiResponse<AdminResponse>> login(
			@Valid @RequestBody AdminLoginRequest body,
			HttpServletRequest request,
			HttpServletResponse response) {
		String loginId = AdminAuthenticationProvider.normalizeLoginId(body.loginId());
		String ipAddress = request.getRemoteAddr();
		if (!rateLimiter.isAllowed(RATE_LIMIT_SCOPE, ipAddress, loginId)) {
			auditLimited(ipAddress, loginId);
			throw new ApiException(
					HttpStatus.TOO_MANY_REQUESTS,
					"RATE_LIMIT_EXCEEDED",
					"잠시 후 다시 시도해 주세요.");
		}

		Authentication authentication;
		try {
			authentication = authenticationManager.authenticate(
					UsernamePasswordAuthenticationToken.unauthenticated(loginId, body.password()));
		}
		catch (AuthenticationException exception) {
			recordLoginFailure(ipAddress, loginId);
			throw invalidCredentials();
		}

		AdminPrincipal principal = (AdminPrincipal) authentication.getPrincipal();
		Admin admin = adminMapper.findById(principal.getAdminId())
				.orElseThrow(() -> new ApiException(
						HttpStatus.SERVICE_UNAVAILABLE,
						"AUTHENTICATION_UNAVAILABLE",
						"로그인을 완료할 수 없습니다."));
		if (!admin.enabled()) {
			recordLoginFailure(ipAddress, loginId);
			throw invalidCredentials();
		}
		auditService.recordRequired(
				"ADMIN_LOGIN_SUCCESS", admin.id(), null, "ADMIN", admin.id(),
				Map.of("ipFingerprint", rateLimiter.fingerprint(ipAddress)));

		rateLimiter.recordSuccess(RATE_LIMIT_SCOPE, ipAddress, loginId);
		sessionAuthenticationStrategy.onAuthentication(authentication, request, response);
		SecurityContext context = SecurityContextHolder.createEmptyContext();
		context.setAuthentication(authentication);
		SecurityContextHolder.setContext(context);
		securityContextRepository.saveContext(context, request, response);

		return ResponseEntity.ok()
				.cacheControl(CacheControl.noStore())
				.body(ApiResponse.of(AdminResponse.from(admin)));
	}

	private void auditLimited(String ipAddress, String loginId) {
		if (rateLimiter.shouldAuditLimited(RATE_LIMIT_SCOPE, ipAddress, loginId)) {
			auditService.recordBestEffort(
					"ADMIN_LOGIN_RATE_LIMITED", null, null, "ADMIN", null,
					Map.of(
							"loginFingerprint", rateLimiter.fingerprint(loginId),
							"ipFingerprint", rateLimiter.fingerprint(ipAddress)));
		}
	}

	private void recordLoginFailure(String ipAddress, String loginId) {
		rateLimiter.recordFailure(RATE_LIMIT_SCOPE, ipAddress, loginId);
		auditService.recordBestEffort(
				"ADMIN_LOGIN_FAILURE", null, null, "ADMIN", null,
				Map.of(
						"loginFingerprint", rateLimiter.fingerprint(loginId),
						"ipFingerprint", rateLimiter.fingerprint(ipAddress)));
	}

	private ApiException invalidCredentials() {
		return new ApiException(
				HttpStatus.UNAUTHORIZED,
				"INVALID_CREDENTIALS",
				"로그인 정보가 올바르지 않습니다.");
	}
}
