package com.ssafy.eyesonu.missingcase.service;

import com.ssafy.eyesonu.audit.service.AuditService;
import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.missingcase.domain.CaseCameraRow;
import com.ssafy.eyesonu.missingcase.domain.SearchConditionRow;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseCameraRequest;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseCameraResponse;
import com.ssafy.eyesonu.missingcase.dto.admin.SearchConditionCreateRequest;
import com.ssafy.eyesonu.missingcase.dto.admin.SearchConditionResponse;
import com.ssafy.eyesonu.missingcase.dto.admin.SearchConditionUpdateRequest;
import com.ssafy.eyesonu.missingcase.mapper.MissingCaseMapper;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class CaseSearchSetupService {

	private final MissingCaseMapper mapper;
	private final CaseQueryService caseQueryService;
	private final AuditService auditService;

	public CaseSearchSetupService(
			MissingCaseMapper mapper, CaseQueryService caseQueryService, AuditService auditService) {
		this.mapper = mapper;
		this.caseQueryService = caseQueryService;
		this.auditService = auditService;
	}

	public List<SearchConditionResponse> findConditions(Long caseId) {
		requireCase(caseId);
		return mapper.findSearchConditions(caseId).stream().map(SearchConditionResponse::from).toList();
	}

	@Transactional
	public SearchConditionResponse createCondition(
			Long caseId, SearchConditionCreateRequest request, Long adminId) {
			requireOpenCase(caseId);
		SearchConditionRow row = new SearchConditionRow();
		row.setCaseId(caseId);
		row.setPrompt(normalizeRequired(request.prompt(), "prompt"));
		row.setExclusionPrompt(normalizeOptional(request.exclusionPrompt()));
		row.setSearchStart(toInstant(request.searchStart()));
		row.setSearchEnd(toInstant(request.searchEnd()));
		row.setSearchArea(normalizeOptional(request.searchArea()));
		row.setSimilarityThreshold(requireThreshold(request.similarityThreshold()));
		validateTimeRange(row.getSearchStart(), row.getSearchEnd());
		mapper.insertSearchCondition(row);
		auditService.recordRequired("SEARCH_CONDITION_CREATED", adminId, caseId, "CASE", caseId,
				Map.of("conditionId", row.getId()));
		return SearchConditionResponse.from(mapper.findSearchCondition(caseId, row.getId()));
	}

	public SearchConditionResponse findCondition(Long caseId, Long conditionId) {
		SearchConditionRow row = requireCondition(caseId, conditionId);
		return SearchConditionResponse.from(row);
	}

	@Transactional
	public SearchConditionResponse updateCondition(
			Long caseId, Long conditionId, SearchConditionUpdateRequest request, Long adminId) {
			requireOpenCase(caseId);
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
		if (request.similarityThreshold() != null) row.setSimilarityThreshold(request.similarityThreshold());
		validateTimeRange(row.getSearchStart(), row.getSearchEnd());
		if (row.getSimilarityThreshold().compareTo(BigDecimal.ZERO) < 0
				|| row.getSimilarityThreshold().compareTo(BigDecimal.ONE) > 0) {
			throw validation("similarityThreshold must be between 0 and 1.");
		}
		mapper.updateSearchCondition(row);
		auditService.recordRequired("SEARCH_CONDITION_UPDATED", adminId, caseId, "CASE", caseId,
				Map.of("conditionId", conditionId));
		return SearchConditionResponse.from(mapper.findSearchCondition(caseId, conditionId));
	}

	@Transactional
	public SearchConditionResponse replaceCondition(
			Long caseId, Long conditionId, SearchConditionCreateRequest request, Long adminId) {
		requireOpenCase(caseId);
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
		row.setSimilarityThreshold(requireThreshold(request.similarityThreshold()));
		validateTimeRange(row.getSearchStart(), row.getSearchEnd());
		mapper.updateSearchCondition(row);
		auditService.recordRequired("SEARCH_CONDITION_UPDATED", adminId, caseId, "CASE", caseId,
				Map.of("conditionId", conditionId));
		return SearchConditionResponse.from(mapper.findSearchCondition(caseId, conditionId));
	}

	@Transactional
	public void deleteCondition(Long caseId, Long conditionId, Long adminId) {
			requireOpenCase(caseId);
		requireCondition(caseId, conditionId);
		if (mapper.countActiveJobsByCondition(caseId, conditionId) > 0) {
			throw new ApiException(HttpStatus.CONFLICT, "RESOURCE_STATE_CONFLICT",
					"A search condition used by an active job cannot be deleted.");
		}
		mapper.deleteSearchCondition(caseId, conditionId);
		auditService.recordRequired("SEARCH_CONDITION_DELETED", adminId, caseId, "CASE", caseId,
				Map.of("conditionId", conditionId));
	}

	public List<CaseCameraResponse> findCameras(Long caseId) {
		requireCase(caseId);
		return mapper.findCaseCameras(caseId).stream().map(CaseCameraResponse::from).toList();
	}

	@Transactional
	public List<CaseCameraResponse> addCameras(
			Long caseId, CaseCameraRequest request, Long adminId) {
			requireOpenCase(caseId);
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
		return findCameras(caseId);
	}

	@Transactional
	public void removeCamera(Long caseId, Long cameraId, Long adminId) {
		requireOpenCase(caseId);
		if (mapper.disableCaseCamera(caseId, cameraId) == 0) {
			throw new ApiException(HttpStatus.NOT_FOUND, "RESOURCE_NOT_FOUND",
					"The camera is not assigned to this case.");
		}
		auditService.recordRequired("CASE_CAMERA_REMOVED", adminId, caseId, "CASE", caseId,
				Map.of("cameraId", cameraId));
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

	private void requireOpenCase(Long caseId) {
		if (caseQueryService.require(caseId).getStatus().name().equals("CLOSED")) {
			throw new ApiException(HttpStatus.UNPROCESSABLE_ENTITY, "BUSINESS_RULE_VIOLATION",
					"A closed case cannot change search settings.");
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

	private BigDecimal requireThreshold(BigDecimal value) {
		if (value == null || value.compareTo(BigDecimal.ZERO) < 0 || value.compareTo(BigDecimal.ONE) > 0) {
			throw validation("similarityThreshold must be between 0 and 1.");
		}
		return value;
	}

	private void validateTimeRange(Instant start, Instant end) {
		if ((start == null) != (end == null)) throw validation("searchStart and searchEnd must be provided together.");
		if (start != null && end.isBefore(start)) throw validation("searchEnd must not be before searchStart.");
	}

	private ApiException validation(String message) {
		return new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_ERROR", message);
	}
}
