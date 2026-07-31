package com.ssafy.eyesonu.admin.service;

import com.ssafy.eyesonu.admin.domain.Admin;
import com.ssafy.eyesonu.admin.domain.AdminRole;
import com.ssafy.eyesonu.admin.dto.AdminCreateRequest;
import com.ssafy.eyesonu.admin.dto.AdminUpdateRequest;
import com.ssafy.eyesonu.admin.mapper.AdminMapper;
import com.ssafy.eyesonu.admin.mapper.AdminMapper.AdminInsertCommand;
import com.ssafy.eyesonu.audit.service.AuditService;
import com.ssafy.eyesonu.auth.security.AdminPrincipal;
import com.ssafy.eyesonu.auth.service.AdminLoginIdPolicy;
import com.ssafy.eyesonu.auth.service.PasswordPolicy;
import com.ssafy.eyesonu.common.exception.ApiException;
import java.util.List;
import java.util.Map;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.session.SessionInformation;
import org.springframework.security.core.session.SessionRegistry;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;
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

	@Transactional(readOnly = true)
	public List<Admin> list() {
		return adminMapper.findAll();
	}

	@Transactional
	public Admin create(AdminPrincipal principal, AdminCreateRequest request) {
		String loginId = AdminLoginIdPolicy.normalize(request.loginId());
		String name = request.name() == null ? "" : request.name().trim();
		if (!AdminLoginIdPolicy.isValid(loginId)) {
			throw validation("로그인 ID는 영문 소문자, 숫자, 점, 밑줄, 하이픈으로 구성된 4~50자여야 합니다.");
		}
		if (!StringUtils.hasText(name) || name.length() > 50) {
			throw validation("이름은 1~50자여야 합니다.");
		}
		PasswordPolicy.validate(request.password());

		if (adminMapper.existsByLoginId(loginId)) {
			throw loginIdConflict();
		}

		AdminInsertCommand command = new AdminInsertCommand(
				loginId,
				passwordEncoder.encode(request.password()),
				name,
				AdminRole.ADMIN,
				true);
		try {
			adminMapper.insert(command);
		}
		catch (DuplicateKeyException exception) {
			throw loginIdConflict();
		}

		Admin created = findManaged(command.getId());
		auditService.recordRequired(
				"ADMIN_ACCOUNT_CREATE",
				principal.getAdminId(),
				null,
				"ADMIN",
				created.id(),
				Map.of(
						"loginId", created.loginId(),
						"role", created.role().name(),
						"enabled", created.enabled()));
		return created;
	}

	@Transactional
	public Admin updateStatus(AdminPrincipal principal, Long adminId, boolean enabled) {
		Admin current = adminMapper.findByIdForUpdate(adminId)
				.orElseThrow(() -> new ApiException(
						HttpStatus.NOT_FOUND,
						"ADMIN_NOT_FOUND",
						"관리자 계정을 찾을 수 없습니다."));

		if (current.enabled() == enabled) {
			if (!enabled) {
				expireSessionsAfterCommit(adminId);
			}
			return current;
		}
		if (!enabled && current.id().equals(principal.getAdminId())) {
			throw new ApiException(
					HttpStatus.CONFLICT,
					"SELF_DEACTIVATION_FORBIDDEN",
					"현재 로그인한 관리자 계정은 비활성화할 수 없습니다.");
		}
		if (!enabled && current.role() == AdminRole.SUPER_ADMIN
				&& adminMapper.findActiveSuperAdminIdsForUpdate().size() <= 1) {
			throw new ApiException(
					HttpStatus.CONFLICT,
					"LAST_SUPER_ADMIN_REQUIRED",
					"마지막 활성 최고 관리자 계정은 비활성화할 수 없습니다.");
		}

		ensureUpdated(adminMapper.updateEnabled(adminId, enabled));
		auditService.recordRequired(
				"ADMIN_ACCOUNT_STATUS_CHANGE",
				principal.getAdminId(),
				null,
				"ADMIN",
				adminId,
				Map.of("enabled", current.enabled()),
				Map.of("enabled", enabled),
				Map.of());

		if (!enabled) {
			expireSessionsAfterCommit(adminId);
		}
		return findManaged(adminId);
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

	private void expireSessionsAfterCommit(Long adminId) {
		if (!TransactionSynchronizationManager.isSynchronizationActive()) {
			expireSessions(adminId);
			return;
		}
		TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
			@Override
			public void afterCommit() {
				expireSessions(adminId);
			}
		});
	}

	private void expireSessions(Long adminId) {
		for (Object registeredPrincipal : sessionRegistry.getAllPrincipals()) {
			if (registeredPrincipal instanceof AdminPrincipal principal
					&& adminId.equals(principal.getAdminId())) {
				expireSessions(principal);
			}
		}
	}

	private Admin findManaged(Long adminId) {
		return adminMapper.findById(adminId).orElseThrow(() -> new ApiException(
				HttpStatus.SERVICE_UNAVAILABLE,
				"ADMIN_UPDATE_FAILED",
				"관리자 계정 정보를 확인할 수 없습니다."));
	}

	private ApiException loginIdConflict() {
		return new ApiException(
				HttpStatus.CONFLICT,
				"ADMIN_LOGIN_ID_CONFLICT",
				"이미 사용 중인 관리자 로그인 ID입니다.");
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
