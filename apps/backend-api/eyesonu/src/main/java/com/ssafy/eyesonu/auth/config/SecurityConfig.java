package com.ssafy.eyesonu.auth.config;

import com.ssafy.eyesonu.admin.mapper.AdminMapper;
import com.ssafy.eyesonu.audit.service.AuditService;
import com.ssafy.eyesonu.auth.device.DeviceKeyAuthenticationFilter;
import com.ssafy.eyesonu.auth.device.MediaServerAuthenticationService;
import com.ssafy.eyesonu.auth.security.AdminAuthenticationProvider;
import com.ssafy.eyesonu.auth.security.AdminAccountStatusFilter;
import com.ssafy.eyesonu.auth.security.AdminPrincipal;
import com.ssafy.eyesonu.auth.security.SecurityErrorWriter;
import com.ssafy.eyesonu.auth.security.SpaCsrfTokenRequestHandler;
import com.ssafy.eyesonu.auth.worker.WorkerKeyAuthenticationFilter;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.annotation.Order;
import org.springframework.core.env.Environment;
import org.springframework.core.env.Profiles;
import org.springframework.http.HttpMethod;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.ProviderManager;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.core.session.SessionRegistry;
import org.springframework.security.core.session.SessionRegistryImpl;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.DelegatingPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.AnonymousAuthenticationFilter;
import org.springframework.security.web.authentication.session.ChangeSessionIdAuthenticationStrategy;
import org.springframework.security.web.authentication.session.CompositeSessionAuthenticationStrategy;
import org.springframework.security.web.authentication.session.ConcurrentSessionControlAuthenticationStrategy;
import org.springframework.security.web.authentication.session.RegisterSessionAuthenticationStrategy;
import org.springframework.security.web.authentication.session.SessionAuthenticationStrategy;
import org.springframework.security.web.context.HttpSessionSecurityContextRepository;
import org.springframework.security.web.context.NullSecurityContextRepository;
import org.springframework.security.web.context.SecurityContextRepository;
import org.springframework.security.web.context.SecurityContextHolderFilter;
import org.springframework.security.web.csrf.CookieCsrfTokenRepository;
import org.springframework.security.web.csrf.CsrfAuthenticationStrategy;
import org.springframework.security.web.session.HttpSessionEventPublisher;
import tools.jackson.databind.ObjectMapper;

@Configuration
public class SecurityConfig {

	@Bean
	PasswordEncoder passwordEncoder() {
		Map<String, PasswordEncoder> encoders = new LinkedHashMap<>();
		encoders.put("bcrypt", new BCryptPasswordEncoder(12));
		return new DelegatingPasswordEncoder("bcrypt", encoders);
	}

	@Bean
	AdminAuthenticationProvider adminAuthenticationProvider(
			AdminMapper adminMapper, PasswordEncoder passwordEncoder) {
		return new AdminAuthenticationProvider(adminMapper, passwordEncoder);
	}

	@Bean
	AuthenticationManager authenticationManager(AdminAuthenticationProvider provider) {
		return new ProviderManager(provider);
	}

	@Bean
	SecurityContextRepository securityContextRepository() {
		return new HttpSessionSecurityContextRepository();
	}

	@Bean
	SessionRegistry sessionRegistry() {
		return new SessionRegistryImpl();
	}

	@Bean
	HttpSessionEventPublisher httpSessionEventPublisher() {
		return new HttpSessionEventPublisher();
	}

	@Bean
	CookieCsrfTokenRepository csrfTokenRepository(Environment environment) {
		boolean secure = environment.acceptsProfiles(Profiles.of("prod"));
		CookieCsrfTokenRepository repository = CookieCsrfTokenRepository.withHttpOnlyFalse();
		repository.setCookieCustomizer(cookie -> cookie.path("/").sameSite("Lax").secure(secure));
		return repository;
	}

	@Bean
	SessionAuthenticationStrategy sessionAuthenticationStrategy(
			SessionRegistry sessionRegistry, CookieCsrfTokenRepository csrfTokenRepository) {
		ConcurrentSessionControlAuthenticationStrategy concurrent =
				new ConcurrentSessionControlAuthenticationStrategy(sessionRegistry);
		concurrent.setMaximumSessions(1);
		concurrent.setExceptionIfMaximumExceeded(false);

		return new CompositeSessionAuthenticationStrategy(List.of(
				concurrent,
				new ChangeSessionIdAuthenticationStrategy(),
				new CsrfAuthenticationStrategy(csrfTokenRepository),
				new RegisterSessionAuthenticationStrategy(sessionRegistry)));
	}

	@Bean
	@Order(1)
	SecurityFilterChain workerSecurityFilterChain(
			HttpSecurity http,
			ObjectMapper objectMapper,
			@Value("${worker.authentication.key:}") String workerKey,
			@Value("${worker.authentication.id:recording-ai-worker}") String workerId) throws Exception {
		SecurityErrorWriter errors = new SecurityErrorWriter(objectMapper);
		WorkerKeyAuthenticationFilter workerFilter = new WorkerKeyAuthenticationFilter(
				workerKey, workerId, errors);

		http
				.securityMatcher("/api/v1/internal/recording-analysis-jobs/**")
				.cors(cors -> cors.disable())
				.csrf(csrf -> csrf.disable())
				.httpBasic(basic -> basic.disable())
				.formLogin(form -> form.disable())
				.logout(logout -> logout.disable())
				.requestCache(cache -> cache.disable())
				.securityContext(context -> context
						.securityContextRepository(new NullSecurityContextRepository()))
				.sessionManagement(session -> session
						.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
				.authorizeHttpRequests(authorize -> authorize
						.anyRequest().hasRole("AI_WORKER"))
				.addFilterBefore(workerFilter, AnonymousAuthenticationFilter.class);
		return http.build();
	}

	@Bean
	@Order(2)
	SecurityFilterChain mediaServerSecurityFilterChain(
			HttpSecurity http,
			ObjectMapper objectMapper,
			MediaServerAuthenticationService mediaServerAuthenticationService) throws Exception {
		SecurityErrorWriter errors = new SecurityErrorWriter(objectMapper);
		DeviceKeyAuthenticationFilter deviceKeyFilter = new DeviceKeyAuthenticationFilter(
				mediaServerAuthenticationService, errors);

		http
				.securityMatcher("/api/v1/device/**")
				.cors(cors -> cors.disable())
				.csrf(csrf -> csrf.disable())
				.httpBasic(basic -> basic.disable())
				.formLogin(form -> form.disable())
				.logout(logout -> logout.disable())
				.requestCache(cache -> cache.disable())
				.securityContext(context -> context
						.securityContextRepository(new NullSecurityContextRepository()))
				.sessionManagement(session -> session
						.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
				.exceptionHandling(exceptions -> exceptions
						.authenticationEntryPoint((request, response, exception) -> errors.write(
								response, 401, "AUTHENTICATION_REQUIRED", "미디어 서버 인증이 필요합니다."))
						.accessDeniedHandler((request, response, exception) -> errors.write(
								response, 403, "ACCESS_DENIED", "접근 권한이 없습니다.")))
				.authorizeHttpRequests(authorize -> authorize
						.anyRequest().hasRole("MEDIA_SERVER"))
				.addFilterBefore(deviceKeyFilter, AnonymousAuthenticationFilter.class);

		return http.build();
	}

	@Bean
	@Order(3)
	SecurityFilterChain applicationSecurityFilterChain(
			HttpSecurity http,
			ObjectMapper objectMapper,
			AdminMapper adminMapper,
			SecurityContextRepository securityContextRepository,
			SessionRegistry sessionRegistry,
			CookieCsrfTokenRepository csrfTokenRepository,
			AuditService auditService) throws Exception {
		SecurityErrorWriter errors = new SecurityErrorWriter(objectMapper);
		AdminAccountStatusFilter adminAccountStatusFilter =
				new AdminAccountStatusFilter(adminMapper, objectMapper);

		http
				.cors(cors -> cors.disable())
				.httpBasic(basic -> basic.disable())
				.formLogin(form -> form.disable())
				.requestCache(cache -> cache.disable())
				.securityContext(context -> context
						.securityContextRepository(securityContextRepository))
				.csrf(csrf -> csrf
						.csrfTokenRepository(csrfTokenRepository)
						.csrfTokenRequestHandler(new SpaCsrfTokenRequestHandler())
						.ignoringRequestMatchers(
								"/api/v1/cases/status-inquiries", "/api/v1/device/**",
								"/api/v1/ai-worker/**"))
				.sessionManagement(session -> {
					session.sessionCreationPolicy(SessionCreationPolicy.IF_REQUIRED);
					session.sessionFixation(fixation -> fixation.changeSessionId());
					session.maximumSessions(1)
							.maxSessionsPreventsLogin(false)
							.expiredSessionStrategy(event -> errors.write(
									event.getResponse(),
									401,
									"SESSION_EXPIRED",
									"다른 로그인으로 현재 세션이 종료되었습니다."))
							.sessionRegistry(sessionRegistry);
				})
				.exceptionHandling(exceptions -> exceptions
						.authenticationEntryPoint((request, response, exception) -> errors.write(
								response, 401, "AUTHENTICATION_REQUIRED", "인증이 필요합니다."))
						.accessDeniedHandler((request, response, exception) -> errors.write(
								response, 403, "ACCESS_DENIED", "접근 권한이 없습니다.")))
				.authorizeHttpRequests(authorize -> authorize
						.requestMatchers("/v3/api-docs/**", "/swagger-ui/**", "/swagger-ui.html").permitAll()
						.requestMatchers(HttpMethod.GET, "/api/v1/auth/csrf").permitAll()
						.requestMatchers(HttpMethod.POST, "/api/v1/auth/admin/login").permitAll()
						.requestMatchers(HttpMethod.POST, "/api/v1/cases/status-inquiries").permitAll()
						.requestMatchers("/api/v1/ai-worker/**").permitAll()
						.requestMatchers("/api/v1/device/**").denyAll()
						.requestMatchers("/api/v1/admins/me").hasRole("ADMIN")
						.requestMatchers("/api/v1/admins", "/api/v1/admins/*/status")
								.hasRole("SUPER_ADMIN")
						.requestMatchers("/api/v1/admin/**").hasRole("ADMIN")
						.requestMatchers("/error").permitAll()
						.anyRequest().denyAll())
				.logout(logout -> logout
						.logoutUrl("/api/v1/auth/admin/logout")
						.addLogoutHandler((request, response, authentication) -> {
							if (authentication != null
									&& authentication.getPrincipal() instanceof AdminPrincipal principal) {
								auditService.recordBestEffort(
										"ADMIN_LOGOUT", principal.getAdminId(), null,
										"ADMIN", principal.getAdminId(), Map.of());
							}
						})
						.deleteCookies("EYESONU_SESSION", "XSRF-TOKEN")
						.logoutSuccessHandler((request, response, authentication) -> response.setStatus(204))
						.permitAll())
				.addFilterAfter(adminAccountStatusFilter, SecurityContextHolderFilter.class);

		return http.build();
	}
}
