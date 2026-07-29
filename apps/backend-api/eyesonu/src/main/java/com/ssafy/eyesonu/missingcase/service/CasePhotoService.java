package com.ssafy.eyesonu.missingcase.service;

import com.ssafy.eyesonu.audit.service.AuditService;
import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.missingcase.domain.CaseStatus;
import com.ssafy.eyesonu.missingcase.domain.MissingCaseRow;
import com.ssafy.eyesonu.missingcase.dto.admin.CasePhotoResponse;
import com.ssafy.eyesonu.missingcase.mapper.MissingCaseMapper;
import com.ssafy.eyesonu.storage.StorageObjectUnavailableException;
import com.ssafy.eyesonu.storage.StorageObjectUrlSigner;
import com.ssafy.eyesonu.storage.StorageObjectWriter;
import java.util.Map;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;
import org.springframework.web.multipart.MultipartFile;

@Service
public class CasePhotoService {
	private static final Logger log = LoggerFactory.getLogger(CasePhotoService.class);

	private final MissingCaseMapper mapper;
	private final CasePhotoValidator validator;
	private final StorageObjectWriter objectWriter;
	private final StorageObjectUrlSigner urlSigner;
	private final AuditService auditService;

	public CasePhotoService(
			MissingCaseMapper mapper,
			CasePhotoValidator validator,
			StorageObjectWriter objectWriter,
			StorageObjectUrlSigner urlSigner,
			AuditService auditService) {
		this.mapper = mapper;
		this.validator = validator;
		this.objectWriter = objectWriter;
		this.urlSigner = urlSigner;
		this.auditService = auditService;
	}

	@Transactional
	public CasePhotoResponse put(Long caseId, MultipartFile file, Long adminId) {
		MissingCaseRow row = requireForUpdate(caseId);
		if (row.getStatus() == CaseStatus.CLOSED) {
			throw new ApiException(
					HttpStatus.UNPROCESSABLE_ENTITY,
					"BUSINESS_RULE_VIOLATION",
					"종료된 사건에는 사진을 등록할 수 없습니다.");
		}
		CasePhotoValidator.ValidatedPhoto photo = validator.validate(file);
		String newKey = "cases/%d/photos/%s.%s".formatted(
				caseId, UUID.randomUUID(), photo.extension());
		String previousKey = row.getPhotoS3Key();
		boolean uploaded = false;
		try {
			objectWriter.put(newKey, photo.bytes(), photo.contentType());
			uploaded = true;
			mapper.updatePhoto(caseId, newKey);
			auditService.recordRequired(
					previousKey == null ? "CASE_PHOTO_UPLOADED" : "CASE_PHOTO_REPLACED",
					adminId, caseId, "CASE", caseId,
					Map.of("hasPhoto", previousKey != null), Map.of("hasPhoto", true), Map.of());
			String photoUrl = urlSigner.createGetUrl(newKey);
			synchronizeUpload(newKey, previousKey);
			return new CasePhotoResponse(photoUrl);
		}
		catch (RuntimeException exception) {
			if (uploaded) deleteBestEffort(newKey);
			if (exception instanceof StorageObjectUnavailableException) {
				throw storageUnavailable();
			}
			throw exception;
		}
	}

	@Transactional
	public void delete(Long caseId, Long adminId) {
		MissingCaseRow row = requireForUpdate(caseId);
		String previousKey = row.getPhotoS3Key();
		if (previousKey == null) return;
		mapper.updatePhoto(caseId, null);
		auditService.recordRequired(
				"CASE_PHOTO_DELETED", adminId, caseId, "CASE", caseId,
				Map.of("hasPhoto", true), Map.of("hasPhoto", false), Map.of());
		deleteAfterCommit(previousKey);
	}

	private MissingCaseRow requireForUpdate(Long id) {
		MissingCaseRow row = mapper.findByIdForUpdate(id);
		if (row == null) {
			throw new ApiException(HttpStatus.NOT_FOUND, "RESOURCE_NOT_FOUND", "사건을 찾을 수 없습니다.");
		}
		return row;
	}

	private void deleteBestEffort(String key) {
		try {
			objectWriter.delete(key);
		}
		catch (RuntimeException exception) {
			log.warn("Failed to remove case photo object: key={}", key, exception);
		}
	}

	private void synchronizeUpload(String newKey, String previousKey) {
		if (!TransactionSynchronizationManager.isSynchronizationActive()) {
			if (previousKey != null) deleteBestEffort(previousKey);
			return;
		}
		TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
			@Override
			public void afterCommit() {
				if (previousKey != null) deleteBestEffort(previousKey);
			}

			@Override
			public void afterCompletion(int status) {
				if (status != TransactionSynchronization.STATUS_COMMITTED) deleteBestEffort(newKey);
			}
		});
	}

	private void deleteAfterCommit(String key) {
		if (!TransactionSynchronizationManager.isSynchronizationActive()) {
			deleteBestEffort(key);
			return;
		}
		TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
			@Override
			public void afterCommit() {
				deleteBestEffort(key);
			}
		});
	}

	private ApiException storageUnavailable() {
		return new ApiException(
				HttpStatus.SERVICE_UNAVAILABLE, "STORAGE_UNAVAILABLE", "사진 저장소를 사용할 수 없습니다.");
	}
}
