package com.ssafy.eyesonu.admin.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.ssafy.eyesonu.admin.dto.AdminUpdateRequest;
import com.ssafy.eyesonu.admin.domain.Admin;
import com.ssafy.eyesonu.admin.mapper.AdminMapper;
import com.ssafy.eyesonu.audit.service.AuditService;
import com.ssafy.eyesonu.auth.security.AdminPrincipal;
import com.ssafy.eyesonu.common.exception.ApiException;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.security.core.session.SessionRegistry;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.DelegatingPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;

class AdminServiceTests {

	private AdminMapper adminMapper;
	private AuditService auditService;
	private AdminService adminService;
	private PasswordEncoder passwordEncoder;
	private Admin admin;
	private AdminPrincipal principal;

	@BeforeEach
	void setUp() {
		adminMapper = mock(AdminMapper.class);
		auditService = mock(AuditService.class);
		SessionRegistry sessionRegistry = mock(SessionRegistry.class);
		Map<String, PasswordEncoder> encoders = new LinkedHashMap<>();
		encoders.put("bcrypt", new BCryptPasswordEncoder(4));
		passwordEncoder = new DelegatingPasswordEncoder("bcrypt", encoders);
		adminService = new AdminService(adminMapper, passwordEncoder, auditService, sessionRegistry);
		admin = new Admin(1L, "admin", passwordEncoder.encode("current-password!"), "Admin");
		principal = new AdminPrincipal(1L, "admin");
		when(adminMapper.findById(1L)).thenReturn(Optional.of(admin));
	}

	@Test
	void rejectsWrongCurrentPassword() {
		ApiException exception = assertThrows(ApiException.class, () -> adminService.update(
				principal, new AdminUpdateRequest(null, "wrong-password!", "new-password!!")));
		assertEquals("CURRENT_PASSWORD_MISMATCH", exception.getCode());
	}

	@Test
	void updatesPasswordAndRequiresReauthentication() {
		when(adminMapper.updatePassword(eq(1L), any())).thenReturn(1);
		when(adminMapper.findById(1L))
				.thenReturn(Optional.of(admin))
				.thenReturn(Optional.of(new Admin(1L, "admin", "changed", "Admin")));

		AdminService.UpdateResult result = adminService.update(
				principal,
				new AdminUpdateRequest(null, "current-password!", "new-password!!"));

		assertTrue(result.passwordChanged());
		verify(adminMapper).updatePassword(eq(1L), any());
		verify(auditService).recordRequired(
				eq("ADMIN_PASSWORD_CHANGE"), eq(1L), eq(null), eq("ADMIN"), eq(1L), eq(Map.of()));
	}
}
