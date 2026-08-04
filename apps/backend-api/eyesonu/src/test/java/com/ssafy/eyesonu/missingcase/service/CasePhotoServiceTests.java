package com.ssafy.eyesonu.missingcase.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.inOrder;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import com.ssafy.eyesonu.common.config.properties.MinioProperties;
import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.missingcase.domain.CasePhotoState;
import com.ssafy.eyesonu.missingcase.domain.CaseStatus;
import com.ssafy.eyesonu.missingcase.mapper.MissingCaseMapper;
import com.ssafy.eyesonu.storage.StorageObjectUnavailableException;
import com.ssafy.eyesonu.storage.StorageObjectUrlSigner;
import com.ssafy.eyesonu.storage.StorageObjectWriter;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.mockito.InOrder;
import org.springframework.dao.DataAccessResourceFailureException;
import org.springframework.mock.web.MockMultipartFile;

class CasePhotoServiceTests {

	private MissingCaseMapper mapper;
	private StorageObjectWriter objectWriter;
	private StorageObjectUrlSigner urlSigner;
	private CasePhotoMetadataWriter metadataWriter;
	private CasePhotoService service;

	@BeforeEach
	void setUp() {
		mapper = mock(MissingCaseMapper.class);
		objectWriter = mock(StorageObjectWriter.class);
		urlSigner = mock(StorageObjectUrlSigner.class);
		metadataWriter = mock(CasePhotoMetadataWriter.class);
		when(mapper.findPhotoState(1L)).thenReturn(state(CaseStatus.SEARCHING, "cases/1/photos/old.jpg"));
		when(urlSigner.createGetUrl(anyString())).thenReturn("https://storage.example/photo");
		MinioProperties properties = new MinioProperties();
		properties.setCasePhotoMaxFileSizeBytes(10L * 1024 * 1024);
		service = new CasePhotoService(
				mapper,
				new CasePhotoValidator(properties),
				objectWriter,
				urlSigner,
				metadataWriter);
	}

	@Test
	void uploadsSignsCommitsMetadataThenRemovesPreviousObject() {
		when(metadataWriter.replace(eq(1L), anyString(), eq(7L)))
				.thenReturn("cases/1/photos/old.jpg");
		ArgumentCaptor<String> newKey = ArgumentCaptor.forClass(String.class);

		assertEquals("https://storage.example/photo", service.put(1L, jpeg(), 7L).photoUrl());

		InOrder order = inOrder(mapper, objectWriter, urlSigner, metadataWriter);
		order.verify(mapper).findPhotoState(1L);
		order.verify(objectWriter).put(newKey.capture(), any(byte[].class), eq("image/jpeg"));
		order.verify(urlSigner).createGetUrl(newKey.getValue());
		order.verify(metadataWriter).replace(1L, newKey.getValue(), 7L);
		order.verify(objectWriter).delete("cases/1/photos/old.jpg");
	}

	@Test
	void metadataFailureCompensatesNewUpload() {
		when(metadataWriter.replace(eq(1L), anyString(), eq(7L)))
				.thenThrow(new DataAccessResourceFailureException("database unavailable"));

		assertThrows(DataAccessResourceFailureException.class, () -> service.put(1L, jpeg(), 7L));

		ArgumentCaptor<String> key = ArgumentCaptor.forClass(String.class);
		verify(objectWriter).put(key.capture(), any(byte[].class), eq("image/jpeg"));
		verify(objectWriter).delete(key.getValue());
		verify(objectWriter, never()).delete("cases/1/photos/old.jpg");
	}

	@Test
	void finalClosedValidationCompensatesNewUpload() {
		when(metadataWriter.replace(eq(1L), anyString(), eq(7L))).thenThrow(new ApiException(
				org.springframework.http.HttpStatus.UNPROCESSABLE_ENTITY,
				"BUSINESS_RULE_VIOLATION",
				"종료된 사건에는 사진을 등록할 수 없습니다."));

		ApiException exception = assertThrows(ApiException.class, () -> service.put(1L, jpeg(), 7L));

		assertEquals("BUSINESS_RULE_VIOLATION", exception.getCode());
		ArgumentCaptor<String> key = ArgumentCaptor.forClass(String.class);
		verify(objectWriter).put(key.capture(), any(byte[].class), eq("image/jpeg"));
		verify(objectWriter).delete(key.getValue());
	}

	@Test
	void signingFailureCompensatesUploadWithoutDatabaseWrite() {
		when(urlSigner.createGetUrl(anyString()))
				.thenThrow(new StorageObjectUnavailableException(new IllegalStateException("sign failed")));

		ApiException exception = assertThrows(ApiException.class, () -> service.put(1L, jpeg(), 7L));

		assertEquals("STORAGE_UNAVAILABLE", exception.getCode());
		ArgumentCaptor<String> key = ArgumentCaptor.forClass(String.class);
		verify(objectWriter).put(key.capture(), any(byte[].class), eq("image/jpeg"));
		verify(objectWriter).delete(key.getValue());
		verifyNoInteractions(metadataWriter);
	}

	@Test
	void preflightRejectsClosedCaseBeforeStorageCalls() {
		when(mapper.findPhotoState(1L)).thenReturn(state(CaseStatus.CLOSED, "cases/1/photos/old.jpg"));

		ApiException exception = assertThrows(ApiException.class, () -> service.put(1L, jpeg(), 7L));

		assertEquals("BUSINESS_RULE_VIOLATION", exception.getCode());
		verifyNoInteractions(objectWriter, urlSigner, metadataWriter);
	}

	@Test
	void deletionCommitsMetadataBeforeRemovingObjectAndAllowsClosedCases() {
		when(metadataWriter.remove(1L, 7L)).thenReturn("cases/1/photos/old.jpg");

		service.delete(1L, 7L);

		InOrder order = inOrder(metadataWriter, objectWriter);
		order.verify(metadataWriter).remove(1L, 7L);
		order.verify(objectWriter).delete("cases/1/photos/old.jpg");
	}

	@Test
	void previousObjectCleanupFailureDoesNotFailSuccessfulReplacement() {
		when(metadataWriter.replace(eq(1L), anyString(), eq(7L)))
				.thenReturn("cases/1/photos/old.jpg");
		org.mockito.Mockito.doThrow(new StorageObjectUnavailableException(new IllegalStateException("delete failed")))
				.when(objectWriter).delete("cases/1/photos/old.jpg");

		assertEquals("https://storage.example/photo", service.put(1L, jpeg(), 7L).photoUrl());
	}

	private MockMultipartFile jpeg() {
		return new MockMultipartFile(
				"photo", "photo.jpg", "image/jpeg",
				new byte[] {(byte) 0xff, (byte) 0xd8, (byte) 0xff, 0x01});
	}

	private CasePhotoState state(CaseStatus status, String photoKey) {
		return new CasePhotoState(1L, status, photoKey);
	}
}
