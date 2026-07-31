package com.ssafy.eyesonu.auth.bootstrap;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import com.ssafy.eyesonu.admin.domain.AdminRole;
import com.ssafy.eyesonu.admin.mapper.AdminMapper;
import com.ssafy.eyesonu.admin.mapper.AdminMapper.AdminInsertCommand;
import com.ssafy.eyesonu.audit.service.AuditService;
import com.ssafy.eyesonu.auth.config.AuthProperties;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.security.crypto.password.PasswordEncoder;

class AdminBootstrapInitializerTests {

	private AdminMapper adminMapper;
	private PasswordEncoder passwordEncoder;
	private AuditService auditService;
	private AuthProperties properties;
	private AdminBootstrapInitializer initializer;

	@BeforeEach
	void setUp() {
		adminMapper = mock(AdminMapper.class);
		passwordEncoder = mock(PasswordEncoder.class);
		auditService = mock(AuditService.class);
		properties = new AuthProperties();
		properties.getBootstrap().setLoginId("  Root.Admin  ");
		properties.getBootstrap().setPassword("bootstrap-password!");
		properties.getBootstrap().setName("  Root Administrator  ");
		when(passwordEncoder.encode("bootstrap-password!")).thenReturn("encoded");
		initializer = new AdminBootstrapInitializer(
				adminMapper, passwordEncoder, properties, auditService);
	}

	@Test
	void createsFirstAccountAsEnabledSuperAdmin() {
		when(adminMapper.count()).thenReturn(0L);
		doAnswer(invocation -> {
			AdminInsertCommand command = invocation.getArgument(0);
			command.setId(7L);
			return null;
		}).when(adminMapper).insert(any());

		initializer.run(null);

		ArgumentCaptor<AdminInsertCommand> command = ArgumentCaptor.forClass(AdminInsertCommand.class);
		verify(adminMapper).insert(command.capture());
		assertEquals("root.admin", command.getValue().getLoginId());
		assertEquals("Root Administrator", command.getValue().getName());
		assertEquals("encoded", command.getValue().getPasswordHash());
		assertEquals(AdminRole.SUPER_ADMIN, command.getValue().getRole());
		assertTrue(command.getValue().isEnabled());
		verify(auditService).recordRequired(
				"ADMIN_BOOTSTRAP", 7L, null, "ADMIN", 7L, Map.of("loginId", "root.admin"));
	}

	@Test
	void doesNotCreateAnotherBootstrapAccountWhenAnyAdminExists() {
		when(adminMapper.count()).thenReturn(1L);

		initializer.run(null);

		verifyNoInteractions(passwordEncoder, auditService);
	}
}
