package com.ssafy.eyesonu.admin.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import com.ssafy.eyesonu.admin.domain.Admin;
import com.ssafy.eyesonu.admin.domain.AdminRole;
import com.ssafy.eyesonu.admin.dto.AdminCreateRequest;
import com.ssafy.eyesonu.admin.dto.AdminUpdateRequest;
import com.ssafy.eyesonu.admin.mapper.AdminMapper;
import com.ssafy.eyesonu.admin.mapper.AdminMapper.AdminInsertCommand;
import com.ssafy.eyesonu.audit.service.AuditService;
import com.ssafy.eyesonu.auth.security.AdminPrincipal;
import com.ssafy.eyesonu.common.exception.ApiException;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.security.core.session.SessionInformation;
import org.springframework.security.core.session.SessionRegistry;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.DelegatingPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.dao.DuplicateKeyException;

class AdminServiceTests {

	private AdminMapper adminMapper;
	private AuditService auditService;
	private SessionRegistry sessionRegistry;
	private AdminService adminService;
	private PasswordEncoder passwordEncoder;
	private Admin admin;
	private AdminPrincipal principal;

	@BeforeEach
	void setUp() {
		adminMapper = mock(AdminMapper.class);
		auditService = mock(AuditService.class);
		sessionRegistry = mock(SessionRegistry.class);
		Map<String, PasswordEncoder> encoders = new LinkedHashMap<>();
		encoders.put("bcrypt", new BCryptPasswordEncoder(4));
		passwordEncoder = new DelegatingPasswordEncoder("bcrypt", encoders);
		adminService = new AdminService(adminMapper, passwordEncoder, auditService, sessionRegistry);
		admin = admin(1L, "admin", AdminRole.ADMIN, true);
		principal = new AdminPrincipal(1L, "admin", AdminRole.ADMIN);
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
				.thenReturn(Optional.of(new Admin(
						1L, "admin", "changed", "Admin", AdminRole.ADMIN, true, admin.createdAt())));

		AdminService.UpdateResult result = adminService.update(
				principal,
				new AdminUpdateRequest(null, "current-password!", "new-password!!"));

		assertTrue(result.passwordChanged());
		verify(adminMapper).updatePassword(eq(1L), any());
		verify(auditService).recordRequired(
				eq("ADMIN_PASSWORD_CHANGE"), eq(1L), eq(null), eq("ADMIN"), eq(1L), eq(Map.of()));
	}

	@Test
	void createsNormalizedEnabledAdminWithHashedPasswordAndSafeAuditDetail() {
		AdminPrincipal superAdmin = new AdminPrincipal(1L, "root", AdminRole.SUPER_ADMIN);
		Admin created = new Admin(
				10L,
				"new.admin",
				"stored-hash",
				"New Admin",
				AdminRole.ADMIN,
				true,
				Instant.parse("2026-07-31T00:00:00Z"));
		when(adminMapper.existsByLoginId("new.admin")).thenReturn(false);
		org.mockito.Mockito.doAnswer(invocation -> {
			AdminInsertCommand command = invocation.getArgument(0);
			command.setId(10L);
			return null;
		}).when(adminMapper).insert(any());
		when(adminMapper.findById(10L)).thenReturn(Optional.of(created));

		Admin result = adminService.create(
				superAdmin,
				new AdminCreateRequest("  New.Admin  ", "  New Admin  ", "initial-password!"));

		assertEquals(created, result);
		ArgumentCaptor<AdminInsertCommand> command = ArgumentCaptor.forClass(AdminInsertCommand.class);
		verify(adminMapper).insert(command.capture());
		assertEquals("new.admin", command.getValue().getLoginId());
		assertEquals("New Admin", command.getValue().getName());
		assertEquals(AdminRole.ADMIN, command.getValue().getRole());
		assertTrue(command.getValue().isEnabled());
		assertNotEquals("initial-password!", command.getValue().getPasswordHash());
		assertTrue(passwordEncoder.matches(
				"initial-password!", command.getValue().getPasswordHash()));
		verify(auditService).recordRequired(
				"ADMIN_ACCOUNT_CREATE",
				1L,
				null,
				"ADMIN",
				10L,
				Map.of("loginId", "new.admin", "role", "ADMIN", "enabled", true));
	}

	@Test
	void rejectsDuplicateLoginIdBeforeEncodingOrInsert() {
		when(adminMapper.existsByLoginId("duplicate")).thenReturn(true);

		ApiException exception = assertThrows(ApiException.class, () -> adminService.create(
				new AdminPrincipal(1L, "root", AdminRole.SUPER_ADMIN),
				new AdminCreateRequest("duplicate", "Admin", "initial-password!")));

		assertEquals("ADMIN_LOGIN_ID_CONFLICT", exception.getCode());
		verify(adminMapper, never()).insert(any());
		verifyNoInteractions(auditService);
	}

	@Test
	void mapsConcurrentDuplicateInsertToStableConflict() {
		when(adminMapper.existsByLoginId("duplicate")).thenReturn(false);
		org.mockito.Mockito.doThrow(new DuplicateKeyException("duplicate login ID"))
				.when(adminMapper).insert(any());

		ApiException exception = assertThrows(ApiException.class, () -> adminService.create(
				new AdminPrincipal(1L, "root", AdminRole.SUPER_ADMIN),
				new AdminCreateRequest("duplicate", "Admin", "initial-password!")));

		assertEquals("ADMIN_LOGIN_ID_CONFLICT", exception.getCode());
		verifyNoInteractions(auditService);
	}

	@Test
	void sameStatusIsIdempotentWithoutAuditOrSessionExpiry() {
		when(adminMapper.findByIdForUpdate(2L))
				.thenReturn(Optional.of(admin(2L, "other", AdminRole.ADMIN, true)));

		Admin result = adminService.updateStatus(
				new AdminPrincipal(1L, "root", AdminRole.SUPER_ADMIN), 2L, true);

		assertTrue(result.enabled());
		verify(adminMapper, never()).updateEnabled(any(), eq(true));
		verifyNoInteractions(auditService, sessionRegistry);
	}

	@Test
	void repeatedDisabledStatusReExpiresLateRegisteredSessions() {
		Admin current = admin(2L, "other", AdminRole.ADMIN, false);
		when(adminMapper.findByIdForUpdate(2L)).thenReturn(Optional.of(current));
		AdminPrincipal registered = new AdminPrincipal(2L, "other", AdminRole.ADMIN);
		SessionInformation session = mock(SessionInformation.class);
		when(sessionRegistry.getAllPrincipals()).thenReturn(List.of(registered));
		when(sessionRegistry.getAllSessions(registered, false)).thenReturn(List.of(session));

		Admin result = adminService.updateStatus(
				new AdminPrincipal(1L, "root", AdminRole.SUPER_ADMIN), 2L, false);

		assertFalse(result.enabled());
		verify(adminMapper, never()).updateEnabled(any(), eq(false));
		verifyNoInteractions(auditService);
		verify(session).expireNow();
	}

	@Test
	void rejectsSelfDeactivation() {
		AdminPrincipal superAdmin = new AdminPrincipal(1L, "root", AdminRole.SUPER_ADMIN);
		when(adminMapper.findByIdForUpdate(1L))
				.thenReturn(Optional.of(admin(1L, "root", AdminRole.SUPER_ADMIN, true)));

		ApiException exception = assertThrows(
				ApiException.class, () -> adminService.updateStatus(superAdmin, 1L, false));

		assertEquals("SELF_DEACTIVATION_FORBIDDEN", exception.getCode());
		verify(adminMapper, never()).updateEnabled(any(), eq(false));
	}

	@Test
	void rejectsDeactivationOfLastActiveSuperAdmin() {
		AdminPrincipal actor = new AdminPrincipal(1L, "root", AdminRole.SUPER_ADMIN);
		when(adminMapper.findByIdForUpdate(2L))
				.thenReturn(Optional.of(admin(2L, "other-root", AdminRole.SUPER_ADMIN, true)));
		when(adminMapper.findActiveSuperAdminIdsForUpdate()).thenReturn(List.of(2L));

		ApiException exception = assertThrows(
				ApiException.class, () -> adminService.updateStatus(actor, 2L, false));

		assertEquals("LAST_SUPER_ADMIN_REQUIRED", exception.getCode());
		verify(adminMapper, never()).updateEnabled(any(), eq(false));
	}

	@Test
	void disablingAdminAuditsChangeAndExpiresRegisteredSessions() {
		AdminPrincipal actor = new AdminPrincipal(1L, "root", AdminRole.SUPER_ADMIN);
		Admin current = admin(2L, "other", AdminRole.ADMIN, true);
		Admin disabled = new Admin(
				current.id(), current.loginId(), current.passwordHash(), current.name(),
				current.role(), false, current.createdAt());
		when(adminMapper.findByIdForUpdate(2L)).thenReturn(Optional.of(current));
		when(adminMapper.updateEnabled(2L, false)).thenReturn(1);
		when(adminMapper.findById(2L)).thenReturn(Optional.of(disabled));
		AdminPrincipal registered = new AdminPrincipal(2L, "other", AdminRole.ADMIN);
		SessionInformation session = mock(SessionInformation.class);
		when(sessionRegistry.getAllPrincipals()).thenReturn(List.of(registered));
		when(sessionRegistry.getAllSessions(registered, false)).thenReturn(List.of(session));

		Admin result = adminService.updateStatus(actor, 2L, false);

		assertFalse(result.enabled());
		verify(auditService).recordRequired(
				"ADMIN_ACCOUNT_STATUS_CHANGE",
				1L,
				null,
				"ADMIN",
				2L,
				Map.of("enabled", true),
				Map.of("enabled", false),
				Map.of());
		verify(session).expireNow();
	}

	@Test
	void missingManagedAdminReturnsStableNotFoundCode() {
		when(adminMapper.findByIdForUpdate(99L)).thenReturn(Optional.empty());

		ApiException exception = assertThrows(ApiException.class, () -> adminService.updateStatus(
				new AdminPrincipal(1L, "root", AdminRole.SUPER_ADMIN), 99L, false));

		assertEquals("ADMIN_NOT_FOUND", exception.getCode());
	}

	private Admin admin(Long id, String loginId, AdminRole role, boolean enabled) {
		return new Admin(
				id,
				loginId,
				passwordEncoder.encode("current-password!"),
				"Admin",
				role,
				enabled,
				Instant.parse("2026-07-30T00:00:00Z"));
	}
}
