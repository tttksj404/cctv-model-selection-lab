package com.ssafy.eyesonu.missingcase.service;

import com.ssafy.eyesonu.audit.service.AuditService;
import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.missingcase.domain.CasePhotoState;
import com.ssafy.eyesonu.missingcase.domain.CaseStatus;
import com.ssafy.eyesonu.missingcase.mapper.MissingCaseMapper;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

@Component
public class CasePhotoMetadataWriter {

	private final MissingCaseMapper mapper;
	private final AuditService auditService;

	public CasePhotoMetadataWriter(MissingCaseMapper mapper, AuditService auditService) {
		this.mapper = mapper;
		this.auditService = auditService;
	}

	@Transactional
	public String replace(Long caseId, String newKey, Long adminId) {
		CasePhotoState state = requireForUpdate(caseId);
		if (state.status() == CaseStatus.CLOSED) {
			throw new ApiException(
					HttpStatus.UNPROCESSABLE_ENTITY,
					"BUSINESS_RULE_VIOLATION",
					"종료된 사건에는 사진을 등록할 수 없습니다.");
		}
		String previousKey = state.photoS3Key();
		mapper.updatePhoto(caseId, newKey);
		auditService.recordRequired(
				previousKey == null ? "CASE_PHOTO_UPLOADED" : "CASE_PHOTO_REPLACED",
				adminId, caseId, "CASE", caseId,
				Map.of("hasPhoto", previousKey != null), Map.of("hasPhoto", true), Map.of());
		return previousKey;
	}

	@Transactional
	public String remove(Long caseId, Long adminId) {
		CasePhotoState state = requireForUpdate(caseId);
		String previousKey = state.photoS3Key();
		if (previousKey == null) return null;
		mapper.updatePhoto(caseId, null);
		auditService.recordRequired(
				"CASE_PHOTO_DELETED", adminId, caseId, "CASE", caseId,
				Map.of("hasPhoto", true), Map.of("hasPhoto", false), Map.of());
		return previousKey;
	}

	private CasePhotoState requireForUpdate(Long id) {
		CasePhotoState state = mapper.findPhotoStateForUpdate(id);
		if (state == null) {
			throw new ApiException(HttpStatus.NOT_FOUND, "RESOURCE_NOT_FOUND", "사건을 찾을 수 없습니다.");
		}
		return state;
	}
}
