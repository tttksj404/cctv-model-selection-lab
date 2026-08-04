package com.ssafy.eyesonu.missingcase.service;

import com.ssafy.eyesonu.audit.service.AuditService;
import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.missingcase.domain.CaseCameraRow;
import com.ssafy.eyesonu.missingcase.domain.CaseStatus;
import com.ssafy.eyesonu.missingcase.domain.MissingCaseRow;
import com.ssafy.eyesonu.missingcase.domain.SearchConditionRow;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseCameraRequest;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseCameraResponse;
import com.ssafy.eyesonu.missingcase.dto.admin.SearchConditionCreateRequest;
import com.ssafy.eyesonu.missingcase.dto.admin.SearchConditionResponse;
import com.ssafy.eyesonu.missingcase.dto.admin.SearchConditionUpdateRequest;
import com.ssafy.eyesonu.missingcase.mapper.MissingCaseMapper;
import com.ssafy.eyesonu.missingcase.messaging.SearchTargetEventPublisher;
import java.time.Instant;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class CaseSearchSetupService {

	private final MissingCaseMapper mapper;
	private final CaseQueryService caseQueryService;
	private final AuditService auditService;
	private final SearchTargetEventPublisher searchTargetEventPublisher;
	private final RealtimePromptNormalizer promptNormalizer;

	public CaseSearchSetupService(
			MissingCaseMapper mapper, CaseQueryService caseQueryService, AuditService auditService,
			SearchTargetEventPublisher searchTargetEventPublisher,
			RealtimePromptNormalizer promptNormalizer) {
		this.mapper = mapper;
		this.caseQueryService = caseQueryService;
		this.auditService = auditService;
		this.searchTargetEventPublisher = searchTargetEventPublisher;
		this.promptNormalizer = promptNormalizer;
	}

	public List<SearchConditionResponse> findConditions(Long caseId) {
		requireCase(caseId);
		return mapper.findSearchConditions(caseId).stream().map(this::toResponse).toList();
	}

	@Transactional
	public SearchConditionResponse createCondition(
			Long caseId, SearchConditionCreateRequest request, Long adminId) {
		MissingCaseRow missingCase = requireOpenCaseForUpdate(caseId);
		SearchConditionRow row = new SearchConditionRow();
		row.setCaseId(caseId);
		row.setPrompt(normalizeRequired(request.prompt(), "prompt"));
		row.setExclusionPrompt(normalizeOptional(request.exclusionPrompt()));
		row.setSearchStart(toInstant(request.searchStart()));
		row.setSearchEnd(toInstant(request.searchEnd()));
		row.setSearchArea(normalizeOptional(request.searchArea()));
		validateTimeRange(row.getSearchStart(), row.getSearchEnd());
		validateRealtimePrompts(row.getPrompt(), row.getExclusionPrompt());
		mapper.insertSearchCondition(row);
		auditService.recordRequired("SEARCH_CONDITION_CREATED", adminId, caseId, "CASE", caseId,
				Map.of("conditionId", row.getId()));
		publishIfSearching(missingCase);
		return toResponse(mapper.findSearchCondition(caseId, row.getId()));
	}

	public SearchConditionResponse findCondition(Long caseId, Long conditionId) {
		SearchConditionRow row = requireCondition(caseId, conditionId);
		return toResponse(row);
	}

	@Transactional
	public SearchConditionResponse updateCondition(
			Long caseId, Long conditionId, SearchConditionUpdateRequest request, Long adminId) {
		MissingCaseRow missingCase = requireOpenCaseForUpdate(caseId);
		SearchConditionRow row = requireCondition(caseId, conditionId);
		if (mapper.countActiveJobsByCondition(caseId, conditionId) > 0) {
			throw new ApiException(HttpStatus.CONFLICT, "RESOURCE_STATE_CONFLICT",
					"A search condition used by an active job cannot be updated.");
		}
		if (request.prompt() != null) row.setPrompt(normalizeRequired(request.prompt(), "prompt"));
		if (request.exclusionPrompt() != null) row.setExclusionPrompt(normalizeOptional(request.exclusionPrompt()));
		if (request.searchStart() != null) row.setSearchStart(request.searchStart().toInstant());
		if (request.searchEnd() != null) row.setSearchEnd(request.searchEnd().toInstant());
		if (request.searchArea() != null) row.setSearchArea(normalizeOptional(request.searchArea()));
		validateTimeRange(row.getSearchStart(), row.getSearchEnd());
		validateRealtimePrompts(row.getPrompt(), row.getExclusionPrompt());
		mapper.updateSearchCondition(row);
		auditService.recordRequired("SEARCH_CONDITION_UPDATED", adminId, caseId, "CASE", caseId,
				Map.of("conditionId", conditionId));
		publishIfSearching(missingCase);
		return toResponse(mapper.findSearchCondition(caseId, conditionId));
	}

	@Transactional
	public SearchConditionResponse replaceCondition(
			Long caseId, Long conditionId, SearchConditionCreateRequest request, Long adminId) {
		MissingCaseRow missingCase = requireOpenCaseForUpdate(caseId);
		SearchConditionRow row = requireCondition(caseId, conditionId);
		if (mapper.countActiveJobsByCondition(caseId, conditionId) > 0) {
			throw new ApiException(HttpStatus.CONFLICT, "RESOURCE_STATE_CONFLICT",
					"A search condition used by an active job cannot be updated.");
		}
		row.setPrompt(normalizeRequired(request.prompt(), "prompt"));
		row.setExclusionPrompt(normalizeOptional(request.exclusionPrompt()));
		row.setSearchStart(toInstant(request.searchStart()));
		row.setSearchEnd(toInstant(request.searchEnd()));
		row.setSearchArea(normalizeOptional(request.searchArea()));
		validateTimeRange(row.getSearchStart(), row.getSearchEnd());
		validateRealtimePrompts(row.getPrompt(), row.getExclusionPrompt());
		mapper.updateSearchCondition(row);
		auditService.recordRequired("SEARCH_CONDITION_UPDATED", adminId, caseId, "CASE", caseId,
				Map.of("conditionId", conditionId));
		publishIfSearching(missingCase);
		return toResponse(mapper.findSearchCondition(caseId, conditionId));
	}

	@Transactional
	public void deleteCondition(Long caseId, Long conditionId, Long adminId) {
		MissingCaseRow missingCase = requireOpenCaseForUpdate(caseId);
		SearchConditionRow condition = requireCondition(caseId, conditionId);
		if (mapper.countActiveJobsByCondition(caseId, conditionId) > 0) {
			throw new ApiException(HttpStatus.CONFLICT, "RESOURCE_STATE_CONFLICT",
					"A search condition used by an active job cannot be deleted.");
		}
		if (missingCase.getStatus() == CaseStatus.SEARCHING && isRealtimeUsable(condition)) {
			boolean hasUsableRemainder = mapper.findSearchConditions(caseId).stream()
					.filter(row -> !Objects.equals(row.getId(), conditionId))
					.anyMatch(this::isRealtimeUsable);
			if (!hasUsableRemainder) {
				throw business("A searching case must keep at least one realtime-usable search condition.");
			}
		}
		mapper.deleteSearchCondition(caseId, conditionId);
		auditService.recordRequired("SEARCH_CONDITION_DELETED", adminId, caseId, "CASE", caseId,
				Map.of("conditionId", conditionId));
		publishIfSearching(missingCase);
	}

	public List<CaseCameraResponse> findCameras(Long caseId) {
		requireCase(caseId);
		return mapper.findCaseCameras(caseId).stream().map(CaseCameraResponse::from).toList();
	}

	@Transactional
	public List<CaseCameraResponse> addCameras(
			Long caseId, CaseCameraRequest request, Long adminId) {
		MissingCaseRow missingCase = requireOpenCaseForUpdate(caseId);
		Set<Long> requested = new HashSet<>(request.cameraIds());
		if (requested.size() != request.cameraIds().size()) {
			throw validation("cameraIds must not contain duplicates.");
		}
		Set<Long> existing = new HashSet<>(mapper.findExistingCameraIds(requested));
		if (!existing.containsAll(requested)) {
			throw new ApiException(HttpStatus.NOT_FOUND, "RESOURCE_NOT_FOUND",
					"One or more cameras were not found.");
		}
		mapper.upsertCaseCameras(caseId, requested);
		auditService.recordRequired("CASE_CAMERAS_UPDATED", adminId, caseId, "CASE", caseId,
				Map.of("cameraIds", requested));
		publishIfSearching(missingCase);
		return mapper.findCaseCameras(caseId).stream().map(CaseCameraResponse::from).toList();
	}

	@Transactional
	public void removeCamera(Long caseId, Long cameraId, Long adminId) {
		MissingCaseRow missingCase = requireOpenCaseForUpdate(caseId);
		if (!mapper.existsActiveCaseCamera(caseId, cameraId)) {
			throw new ApiException(HttpStatus.NOT_FOUND, "RESOURCE_NOT_FOUND",
					"The camera is not assigned to this case.");
		}
		if (missingCase.getStatus() == CaseStatus.SEARCHING
				&& mapper.countActiveCameras(caseId) <= 1) {
			throw business("A searching case must keep at least one active camera.");
		}
		if (mapper.disableCaseCamera(caseId, cameraId) == 0) {
			throw new ApiException(HttpStatus.NOT_FOUND, "RESOURCE_NOT_FOUND",
					"The camera is not assigned to this case.");
		}
		auditService.recordRequired("CASE_CAMERA_REMOVED", adminId, caseId, "CASE", caseId,
				Map.of("cameraId", cameraId));
		publishIfSearching(missingCase);
	}

	private SearchConditionRow requireCondition(Long caseId, Long conditionId) {
		SearchConditionRow row = mapper.findSearchCondition(caseId, conditionId);
		if (row == null) {
			throw new ApiException(HttpStatus.NOT_FOUND, "RESOURCE_NOT_FOUND", "Search condition was not found.");
		}
		return row;
	}

	private void requireCase(Long caseId) {
		caseQueryService.require(caseId);
	}

	private MissingCaseRow requireOpenCaseForUpdate(Long caseId) {
		MissingCaseRow row = mapper.findByIdForUpdate(caseId);
		if (row == null) {
			throw new ApiException(HttpStatus.NOT_FOUND, "RESOURCE_NOT_FOUND", "Case was not found.");
		}
		if (row.getStatus() == CaseStatus.CLOSED) {
			throw new ApiException(HttpStatus.UNPROCESSABLE_ENTITY, "BUSINESS_RULE_VIOLATION",
					"A closed case cannot change search settings.");
		}
		return row;
	}

	private void publishIfSearching(MissingCaseRow row) {
		if (row.getStatus() == CaseStatus.SEARCHING) {
			searchTargetEventPublisher.publishAfterCommit(
					SearchTargetEventPublisher.TARGET_UPDATED, row.getId(), Instant.now());
		}
	}

	private SearchConditionResponse toResponse(SearchConditionRow row) {
		String normalizedPrompt = promptNormalizer.normalizeOrNull(row.getPrompt());
		String normalizedExclusionPrompt = promptNormalizer.normalizeOrNull(row.getExclusionPrompt());
		return SearchConditionResponse.from(
				row,
				normalizedPrompt,
				normalizedExclusionPrompt,
				isRealtimeUsable(row));
	}

	private boolean isRealtimeUsable(SearchConditionRow row) {
		return promptNormalizer.isUsable(row.getPrompt(), row.getExclusionPrompt());
	}

	private void validateRealtimePrompts(String prompt, String exclusionPrompt) {
		if (!promptNormalizer.isUsable(prompt, exclusionPrompt)) {
			throw new ApiException(
					HttpStatus.BAD_REQUEST,
					"REALTIME_PROMPT_INVALID",
					"The search prompt and optional exclusion prompt must use the realtime prompt format.");
		}
	}

	private String normalizeRequired(String value, String field) {
		String normalized = value == null ? null : value.trim();
		if (normalized == null || normalized.isEmpty()) throw validation(field + " must not be blank.");
		return normalized;
	}

	private String normalizeOptional(String value) {
		if (value == null) return null;
		String normalized = value.trim();
		return normalized.isEmpty() ? null : normalized;
	}

	private Instant toInstant(java.time.OffsetDateTime value) {
		return value == null ? null : value.toInstant();
	}

	private void validateTimeRange(Instant start, Instant end) {
		if ((start == null) != (end == null)) throw validation("searchStart and searchEnd must be provided together.");
		if (start != null && end.isBefore(start)) throw validation("searchEnd must not be before searchStart.");
	}

	private ApiException validation(String message) {
		return new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_ERROR", message);
	}

	private ApiException business(String message) {
		return new ApiException(HttpStatus.UNPROCESSABLE_ENTITY, "BUSINESS_RULE_VIOLATION", message);
	}
}
