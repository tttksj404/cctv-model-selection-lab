package com.ssafy.eyesonu.missingcase.service;

import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.missingcase.domain.CasePhotoState;
import com.ssafy.eyesonu.missingcase.domain.CaseStatus;
import com.ssafy.eyesonu.missingcase.dto.admin.CasePhotoResponse;
import com.ssafy.eyesonu.missingcase.mapper.MissingCaseMapper;
import com.ssafy.eyesonu.storage.StorageObjectUnavailableException;
import com.ssafy.eyesonu.storage.StorageObjectUrlSigner;
import com.ssafy.eyesonu.storage.StorageObjectWriter;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

@Service
public class CasePhotoService {
	private static final Logger log = LoggerFactory.getLogger(CasePhotoService.class);

	private final MissingCaseMapper mapper;
	private final CasePhotoValidator validator;
	private final StorageObjectWriter objectWriter;
	private final StorageObjectUrlSigner urlSigner;
	private final CasePhotoMetadataWriter metadataWriter;

	public CasePhotoService(
			MissingCaseMapper mapper,
			CasePhotoValidator validator,
			StorageObjectWriter objectWriter,
			StorageObjectUrlSigner urlSigner,
			CasePhotoMetadataWriter metadataWriter) {
		this.mapper = mapper;
		this.validator = validator;
		this.objectWriter = objectWriter;
		this.urlSigner = urlSigner;
		this.metadataWriter = metadataWriter;
	}

	public CasePhotoResponse put(Long caseId, MultipartFile file, Long adminId) {
		CasePhotoValidator.ValidatedPhoto photo = validator.validate(file);
		requireUploadAllowed(caseId);
		String newKey = "cases/%d/photos/%s.%s".formatted(
				caseId, UUID.randomUUID(), photo.extension());
		String photoUrl;
		try {
			objectWriter.put(newKey, photo.bytes(), photo.contentType());
			photoUrl = urlSigner.createGetUrl(newKey);
		}
		catch (RuntimeException exception) {
			deleteBestEffort(newKey);
			if (exception instanceof StorageObjectUnavailableException) {
				throw storageUnavailable();
			}
			throw exception;
		}

		String previousKey;
		try {
			previousKey = metadataWriter.replace(caseId, newKey, adminId);
		}
		catch (RuntimeException exception) {
			deleteBestEffort(newKey);
			throw exception;
		}
		if (previousKey != null) deleteBestEffort(previousKey);
		return new CasePhotoResponse(photoUrl);
	}

	public void delete(Long caseId, Long adminId) {
		String previousKey = metadataWriter.remove(caseId, adminId);
		if (previousKey != null) deleteBestEffort(previousKey);
	}

	private void requireUploadAllowed(Long id) {
		CasePhotoState state = mapper.findPhotoState(id);
		if (state == null) {
			throw new ApiException(HttpStatus.NOT_FOUND, "RESOURCE_NOT_FOUND", "사건을 찾을 수 없습니다.");
		}
		if (state.status() == CaseStatus.CLOSED) {
			throw new ApiException(
					HttpStatus.UNPROCESSABLE_ENTITY,
					"BUSINESS_RULE_VIOLATION",
					"종료된 사건에는 사진을 등록할 수 없습니다.");
		}
	}

	private void deleteBestEffort(String key) {
		try {
			objectWriter.delete(key);
		}
		catch (RuntimeException exception) {
			log.warn("Failed to remove case photo object: key={}", key, exception);
		}
	}

	private ApiException storageUnavailable() {
		return new ApiException(
				HttpStatus.SERVICE_UNAVAILABLE, "STORAGE_UNAVAILABLE", "사진 저장소를 사용할 수 없습니다.");
	}
}
