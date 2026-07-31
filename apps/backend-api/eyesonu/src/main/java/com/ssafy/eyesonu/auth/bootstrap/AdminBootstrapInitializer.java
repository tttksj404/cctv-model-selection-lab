package com.ssafy.eyesonu.auth.bootstrap;

import com.ssafy.eyesonu.admin.mapper.AdminMapper;
import com.ssafy.eyesonu.admin.mapper.AdminMapper.AdminInsertCommand;
import com.ssafy.eyesonu.admin.domain.AdminRole;
import com.ssafy.eyesonu.audit.service.AuditService;
import com.ssafy.eyesonu.auth.config.AuthProperties;
import com.ssafy.eyesonu.auth.security.AdminAuthenticationProvider;
import com.ssafy.eyesonu.auth.service.PasswordPolicy;
import com.ssafy.eyesonu.auth.service.AdminLoginIdPolicy;
import java.util.Map;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

@Component
@ConditionalOnProperty(prefix = "eyesonu.auth.bootstrap", name = "enabled", havingValue = "true")
public class AdminBootstrapInitializer implements ApplicationRunner {

	private final AdminMapper adminMapper;
	private final PasswordEncoder passwordEncoder;
	private final AuthProperties properties;
	private final AuditService auditService;

	public AdminBootstrapInitializer(
			AdminMapper adminMapper,
			PasswordEncoder passwordEncoder,
			AuthProperties properties,
			AuditService auditService) {
		this.adminMapper = adminMapper;
		this.passwordEncoder = passwordEncoder;
		this.properties = properties;
		this.auditService = auditService;
	}

	@Override
	@Transactional
	public void run(ApplicationArguments args) {
		if (adminMapper.count() > 0) {
			return;
		}

		AuthProperties.Bootstrap bootstrap = properties.getBootstrap();
		String loginId = AdminAuthenticationProvider.normalizeLoginId(bootstrap.getLoginId());
		String name = bootstrap.getName() == null ? "" : bootstrap.getName().trim();
		if (!AdminLoginIdPolicy.isValid(loginId)
				|| !StringUtils.hasText(name)
				|| name.length() > 50) {
			throw new IllegalStateException("Valid administrator bootstrap values are required");
		}
		PasswordPolicy.validate(bootstrap.getPassword());

		AdminInsertCommand command = new AdminInsertCommand(
				loginId,
				passwordEncoder.encode(bootstrap.getPassword()),
				name,
				AdminRole.SUPER_ADMIN,
				true);
		adminMapper.insert(command);
		auditService.recordRequired(
				"ADMIN_BOOTSTRAP",
				command.getId(),
				null,
				"ADMIN",
				command.getId(),
				Map.of("loginId", loginId));
	}
}
