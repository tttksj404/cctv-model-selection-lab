package com.ssafy.eyesonu.admin.service;

import com.ssafy.eyesonu.admin.dto.AdminUpdateRequest;
import com.ssafy.eyesonu.admin.domain.Admin;
import com.ssafy.eyesonu.admin.mapper.AdminMapper;
import com.ssafy.eyesonu.audit.service.AuditService;
import com.ssafy.eyesonu.auth.security.AdminPrincipal;
import com.ssafy.eyesonu.auth.service.PasswordPolicy;
import com.ssafy.eyesonu.common.exception.ApiException;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.session.SessionInformation;
import org.springframework.security.core.session.SessionRegistry;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

@Service
public class AdminService {

	private final AdminMapper adminMapper;
	private final PasswordEncoder passwordEncoder;
	private final AuditService auditService;
	private final SessionRegistry sessionRegistry;

	public AdminService(
			AdminMapper adminMapper,
			PasswordEncoder passwordEncoder,
			AuditService auditService,
			SessionRegistry sessionRegistry) {
		this.adminMapper = adminMapper;
		this.passwordEncoder = passwordEncoder;
		this.auditService = auditService;
		this.sessionRegistry = sessionRegistry;
	}

	public Admin get(Long adminId) {
		return adminMapper.findById(adminId).orElseThrow(() -> new ApiException(
				HttpStatus.UNAUTHORIZED, "AUTHENTICATION_REQUIRED", "관리자 계정을 확인할 수 없습니다."));
	}

	@Transactional
	public UpdateResult update(AdminPrincipal principal, AdminUpdateRequest request) {
		Admin current = get(principal.getAdminId());
		String name = request.name() == null ? null : request.name().trim();
		boolean nameRequested = request.name() != null;
		boolean passwordRequested = request.currentPassword() != null || request.newPassword() != null;

		if (!nameRequested && !passwordRequested) {
			throw validation("변경할 값을 입력해 주세요.");
		}
		if (nameRequested && (!StringUtils.hasText(name) || name.length() > 50)) {
			throw validation("이름은 1~50자여야 합니다.");
		}
		if (passwordRequested
				&& (!StringUtils.hasText(request.currentPassword())
						|| !StringUtils.hasText(request.newPassword()))) {
			throw validation("현재 비밀번호와 새 비밀번호를 함께 입력해 주세요.");
		}

		if (nameRequested) {
			ensureUpdated(adminMapper.updateName(current.id(), name));
			auditService.recordRequired(
					"ADMIN_PROFILE_UPDATE", current.id(), null, "ADMIN", current.id(),
					Map.of("nameChanged", !current.name().equals(name)));
		}

		if (passwordRequested) {
			if (!passwordEncoder.matches(request.currentPassword(), current.passwordHash())) {
				throw new ApiException(
						HttpStatus.BAD_REQUEST,
						"CURRENT_PASSWORD_MISMATCH",
						"현재 비밀번호가 올바르지 않습니다.");
			}
			PasswordPolicy.validate(request.newPassword());
			ensureUpdated(adminMapper.updatePassword(
					current.id(), passwordEncoder.encode(request.newPassword())));
			auditService.recordRequired(
					"ADMIN_PASSWORD_CHANGE", current.id(), null, "ADMIN", current.id(), Map.of());
		}

		Admin updated = get(current.id());
		return new UpdateResult(updated, passwordRequested);
	}

	public void expireSessions(AdminPrincipal principal) {
		for (SessionInformation session : sessionRegistry.getAllSessions(principal, false)) {
			session.expireNow();
		}
	}

	private void ensureUpdated(int updatedRows) {
		if (updatedRows != 1) {
			throw new ApiException(
					HttpStatus.SERVICE_UNAVAILABLE,
					"ADMIN_UPDATE_FAILED",
					"관리자 정보를 변경할 수 없습니다.");
		}
	}

	private ApiException validation(String message) {
		return new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_ERROR", message);
	}

	public record UpdateResult(Admin admin, boolean passwordChanged) {
	}
}
