package com.ssafy.eyesonu.missingcase.service;

import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.missingcase.domain.CaseSortDirection;
import com.ssafy.eyesonu.missingcase.domain.CaseSortField;
import com.ssafy.eyesonu.missingcase.domain.MissingCaseRow;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseDetailResponse;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseListResponse;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseSearchCondition;
import com.ssafy.eyesonu.missingcase.mapper.MissingCaseMapper;
import com.ssafy.eyesonu.storage.StorageObjectUnavailableException;
import com.ssafy.eyesonu.storage.StorageObjectUrlSigner;
import java.time.Instant;
import java.util.List;
import java.util.Locale;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;

@Service
public class CaseQueryService {

	private final MissingCaseMapper mapper;
	private final StorageObjectUrlSigner urlSigner;

	public CaseQueryService(MissingCaseMapper mapper, StorageObjectUrlSigner urlSigner) {
		this.mapper = mapper;
		this.urlSigner = urlSigner;
	}

	public CasePageResult findAll(CaseSearchCondition condition) {
		validatePage(condition.page(), condition.size());
		ParsedSort sort = parseSort(condition.sort());
		String caseNumber = normalizeCaseNumber(condition.caseNumber());
		String missingName = trimToNull(condition.missingName());
		Instant from = condition.reportedFrom() == null ? null : condition.reportedFrom().toInstant();
		Instant to = condition.reportedTo() == null ? null : condition.reportedTo().toInstant();
		if (from != null && to != null && !from.isBefore(to)) {
			throw validation("reportedFrom은 reportedTo보다 빨라야 합니다.");
		}
		long total = mapper.countCases(condition.status(), caseNumber, missingName, from, to);
		long offset = (long) condition.page() * condition.size();
		List<CaseListResponse> cases = total == 0 ? List.of() : mapper.findPage(
				condition.status(), caseNumber, missingName, from, to,
				sort.field(), sort.direction(), condition.size(), offset).stream()
				.map(row -> CaseListResponse.from(row, photoUrl(row)))
				.toList();
		long totalPagesLong = total / condition.size() + (total % condition.size() == 0 ? 0 : 1);
		return new CasePageResult(
				cases, condition.page(), condition.size(), total,
				(int) Math.min(Integer.MAX_VALUE, totalPagesLong), sort.external());
	}

	public CaseDetailResponse findById(Long id) {
		MissingCaseRow row = require(id);
		return CaseDetailResponse.from(row, photoUrl(row));
	}

	public MissingCaseRow require(Long id) {
		MissingCaseRow row = mapper.findById(id);
		if (row == null) {
			throw new ApiException(HttpStatus.NOT_FOUND, "RESOURCE_NOT_FOUND", "사건을 찾을 수 없습니다.");
		}
		return row;
	}

	private String photoUrl(MissingCaseRow row) {
		if (row.getPhotoS3Key() == null) return null;
		try {
			return urlSigner.createGetUrl(row.getPhotoS3Key());
		}
		catch (StorageObjectUnavailableException exception) {
			throw new ApiException(
					HttpStatus.SERVICE_UNAVAILABLE, "STORAGE_UNAVAILABLE", "사진 URL을 생성할 수 없습니다.");
		}
	}

	private String normalizeCaseNumber(String value) {
		String normalized = trimToNull(value);
		return normalized == null ? null : normalized.toUpperCase(Locale.ROOT);
	}

	private String trimToNull(String value) {
		if (value == null || value.trim().isEmpty()) return null;
		return value.trim();
	}

	private void validatePage(int page, int size) {
		if (page < 0 || size < 1 || size > 100) {
			throw validation("page는 0 이상, size는 1~100이어야 합니다.");
		}
	}

	private ParsedSort parseSort(String value) {
		String normalized = value == null || value.isBlank() ? "reportedAt,desc" : value;
		String[] parts = normalized.split(",", -1);
		if (parts.length != 2) throw validation("sort 형식은 {field},{direction}입니다.");
		CaseSortField field = switch (parts[0]) {
			case "reportedAt" -> CaseSortField.REPORTED_AT;
			case "updatedAt" -> CaseSortField.UPDATED_AT;
			case "missingName" -> CaseSortField.MISSING_NAME;
			default -> throw validation("지원하지 않는 정렬 필드입니다.");
		};
		CaseSortDirection direction = switch (parts[1]) {
			case "asc" -> CaseSortDirection.ASC;
			case "desc" -> CaseSortDirection.DESC;
			default -> throw validation("정렬 방향은 asc 또는 desc여야 합니다.");
		};
		return new ParsedSort(field, direction, parts[0] + "," + parts[1]);
	}

	private ApiException validation(String message) {
		return new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_ERROR", message);
	}

	private record ParsedSort(CaseSortField field, CaseSortDirection direction, String external) {
	}
}
