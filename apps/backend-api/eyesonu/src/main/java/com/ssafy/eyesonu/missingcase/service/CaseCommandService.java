package com.ssafy.eyesonu.missingcase.service;

import com.ssafy.eyesonu.audit.service.AuditService;
import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.missingcase.domain.CaseStatus;
import com.ssafy.eyesonu.missingcase.domain.MissingCaseRow;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseCloseRequest;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseCreateRequest;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseCreateResponse;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseStateResponse;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseStatusUpdateRequest;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseUpdateRequest;
import com.ssafy.eyesonu.missingcase.mapper.MissingCaseMapper;
import com.ssafy.eyesonu.missingcase.messaging.SearchTargetEventPublisher;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class CaseCommandService {

	private static final int CASE_NUMBER_ATTEMPTS = 5;

	private final MissingCaseMapper mapper;
	private final CaseRequestValidator validator;
	private final CaseNumberGenerator caseNumberGenerator;
	private final CaseRegistrationWriter registrationWriter;
	private final AuditService auditService;
	private final SearchTargetEventPublisher searchTargetEventPublisher;

	public CaseCommandService(
			MissingCaseMapper mapper,
			CaseRequestValidator validator,
			CaseNumberGenerator caseNumberGenerator,
			CaseRegistrationWriter registrationWriter,
			AuditService auditService,
			SearchTargetEventPublisher searchTargetEventPublisher) {
		this.mapper = mapper;
		this.validator = validator;
		this.caseNumberGenerator = caseNumberGenerator;
		this.registrationWriter = registrationWriter;
		this.auditService = auditService;
		this.searchTargetEventPublisher = searchTargetEventPublisher;
	}

	public CaseCreateResponse create(CaseCreateRequest request, Long adminId) {
		MissingCaseRow normalized = validator.normalizeCreate(request);
		for (int attempt = 0; attempt < CASE_NUMBER_ATTEMPTS; attempt++) {
			normalized.setId(null);
			normalized.setReporterId(null);
			normalized.setCaseNumber(caseNumberGenerator.generate());
			try {
				MissingCaseRow created = registrationWriter.write(normalized, adminId);
				return new CaseCreateResponse(
						created.getId(), created.getCaseNumber(), created.getStatus(), created.getReportedAt());
			}
			catch (CaseNumberCollisionException exception) {
				// Retry with a newly generated number after the independent attempt rolls back.
			}
		}
		throw new ApiException(
				HttpStatus.SERVICE_UNAVAILABLE,
				"CASE_NUMBER_ALLOCATION_FAILED",
				"사건번호를 발급할 수 없습니다.");
	}

	@Transactional
	public Long update(Long caseId, CaseUpdateRequest request, Long adminId) {
		MissingCaseRow row = requireForUpdate(caseId);
		rejectClosed(row);
		Map<String, Object> before = CaseAuditValues.snapshot(row);
		validator.applyUpdate(row, request);
		mapper.updateReporter(row);
		mapper.updateCase(row);
		auditService.recordRequired(
				"CASE_UPDATED", adminId, caseId, "CASE", caseId,
				before, CaseAuditValues.snapshot(row), Map.of());
		return caseId;
	}

	@Transactional
	public CaseStateResponse updateStatus(Long caseId, CaseStatusUpdateRequest request, Long adminId) {
		MissingCaseRow row = requireForUpdate(caseId);
		if (request.status() == CaseStatus.CLOSED) {
			throw validation("CLOSED 전환은 사건 종료 API를 사용해야 합니다.");
		}
		if (!row.getStatus().canTransitionTo(request.status())) {
			throw business("허용되지 않는 사건 상태 전이입니다.");
		}
		if (row.getStatus() == CaseStatus.RECEIVED && request.status() == CaseStatus.SEARCHING) {
			if (mapper.countSearchConditions(caseId) == 0 || mapper.countActiveCameras(caseId) == 0) {
				throw business("탐색 조건과 활성 카메라를 각각 하나 이상 등록해야 합니다.");
			}
		}
		CaseStatus previous = row.getStatus();
		mapper.updateStatus(caseId, request.status(), null);
		auditService.recordRequired(
				"CASE_STATUS_CHANGED", adminId, caseId, "CASE", caseId,
				Map.of("status", previous), Map.of("status", request.status()),
				Map.of("reason", request.reason().trim()));
		MissingCaseRow updated = mapper.findById(caseId);
		publishSearchTargetEvent(previous, request.status(), updated);
		return state(updated);
	}

	@Transactional
	public CaseStateResponse close(Long caseId, CaseCloseRequest request, Long adminId) {
		MissingCaseRow row = requireForUpdate(caseId);
		if (row.getStatus() == CaseStatus.CLOSED) {
			throw new ApiException(
					HttpStatus.CONFLICT, "RESOURCE_STATE_CONFLICT", "이미 종료된 사건입니다.");
		}
		long pendingCandidates = mapper.countPendingCandidates(caseId);
		long activeJobs = mapper.countActiveJobs(caseId);
		if (!request.force() && (pendingCandidates > 0 || activeJobs > 0)) {
			throw new ApiException(
					HttpStatus.CONFLICT,
					"CASE_CLOSE_CONFLICT",
					"미처리 후보 또는 실행 중인 작업이 있습니다.");
		}
		int cancelledJobs = request.force() ? mapper.cancelActiveJobs(caseId) : 0;
		Instant closedAt = Instant.now();
		mapper.updateStatus(caseId, CaseStatus.CLOSED, closedAt);
		Map<String, Object> detail = new LinkedHashMap<>();
		detail.put("reason", request.reason().trim());
		detail.put("force", request.force());
		detail.put("pendingCandidates", pendingCandidates);
		detail.put("cancelledJobs", cancelledJobs);
		auditService.recordRequired(
				"CASE_CLOSED", adminId, caseId, "CASE", caseId,
				Map.of("status", row.getStatus()), Map.of("status", CaseStatus.CLOSED), detail);
		return state(mapper.findById(caseId));
	}

	private MissingCaseRow requireForUpdate(Long id) {
		MissingCaseRow row = mapper.findByIdForUpdate(id);
		if (row == null) {
			throw new ApiException(HttpStatus.NOT_FOUND, "RESOURCE_NOT_FOUND", "사건을 찾을 수 없습니다.");
		}
		return row;
	}

	private void rejectClosed(MissingCaseRow row) {
		if (row.getStatus() == CaseStatus.CLOSED) {
			throw business("종료된 사건은 수정할 수 없습니다.");
		}
	}

	private CaseStateResponse state(MissingCaseRow row) {
		return new CaseStateResponse(row.getId(), row.getStatus(), row.getClosedAt(), row.getUpdatedAt());
	}

	private void publishSearchTargetEvent(CaseStatus previous, CaseStatus current, MissingCaseRow updated) {
		if (previous != CaseStatus.SEARCHING && current == CaseStatus.SEARCHING) {
			searchTargetEventPublisher.publishAfterCommit(
					SearchTargetEventPublisher.TARGET_UPDATED, updated.getId(), updated.getUpdatedAt());
		}
		if (previous == CaseStatus.SEARCHING && current != CaseStatus.SEARCHING) {
			searchTargetEventPublisher.publishAfterCommit(
					SearchTargetEventPublisher.TARGET_DISABLED, updated.getId(), updated.getUpdatedAt());
		}
	}

	private ApiException validation(String message) {
		return new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_ERROR", message);
	}

	private ApiException business(String message) {
		return new ApiException(HttpStatus.UNPROCESSABLE_ENTITY, "BUSINESS_RULE_VIOLATION", message);
	}
}
