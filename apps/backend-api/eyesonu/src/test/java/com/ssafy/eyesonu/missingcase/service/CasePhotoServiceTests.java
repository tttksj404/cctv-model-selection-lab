package com.ssafy.eyesonu.missingcase.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.ssafy.eyesonu.audit.service.AuditService;
import com.ssafy.eyesonu.common.config.properties.S3Properties;
import com.ssafy.eyesonu.missingcase.domain.CaseStatus;
import com.ssafy.eyesonu.missingcase.domain.MissingCaseRow;
import com.ssafy.eyesonu.missingcase.mapper.MissingCaseMapper;
import com.ssafy.eyesonu.storage.StorageObjectUrlSigner;
import com.ssafy.eyesonu.storage.StorageObjectWriter;
import java.util.List;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.dao.DataAccessResourceFailureException;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;

class CasePhotoServiceTests {

	private MissingCaseMapper mapper;
	private StorageObjectWriter objectWriter;
	private CasePhotoService service;

	@BeforeEach
	void setUp() {
		mapper = mock(MissingCaseMapper.class);
		objectWriter = mock(StorageObjectWriter.class);
		StorageObjectUrlSigner urlSigner = mock(StorageObjectUrlSigner.class);
		when(urlSigner.createGetUrl(anyString())).thenReturn("https://storage.example/photo");
		S3Properties properties = new S3Properties();
		properties.setCasePhotoMaxFileSizeBytes(10L * 1024 * 1024);
		service = new CasePhotoService(
				mapper,
				new CasePhotoValidator(properties),
				objectWriter,
				urlSigner,
				mock(AuditService.class));
		TransactionSynchronizationManager.initSynchronization();
	}

	@AfterEach
	void tearDown() {
		if (TransactionSynchronizationManager.isSynchronizationActive()) {
			TransactionSynchronizationManager.clearSynchronization();
		}
	}

	@Test
	void replacementRemovesPreviousObjectOnlyAfterDatabaseCommit() {
		when(mapper.findByIdForUpdate(1L)).thenReturn(row(CaseStatus.SEARCHING, "cases/1/photos/old.jpg"));

		assertEquals("https://storage.example/photo", service.put(1L, jpeg(), 7L).photoUrl());
		verify(objectWriter, never()).delete(anyString());

		List<TransactionSynchronization> synchronizations =
				TransactionSynchronizationManager.getSynchronizations();
		synchronizations.forEach(TransactionSynchronization::afterCommit);
		synchronizations.forEach(it -> it.afterCompletion(TransactionSynchronization.STATUS_COMMITTED));

		verify(objectWriter).delete("cases/1/photos/old.jpg");
	}

	@Test
	void databaseFailureCompensatesNewUpload() {
		when(mapper.findByIdForUpdate(1L)).thenReturn(row(CaseStatus.RECEIVED, null));
		org.mockito.Mockito.doThrow(new DataAccessResourceFailureException("database unavailable"))
				.when(mapper).updatePhoto(eq(1L), anyString());

		org.junit.jupiter.api.Assertions.assertThrows(
				DataAccessResourceFailureException.class,
				() -> service.put(1L, jpeg(), 7L));

		ArgumentCaptor<String> key = ArgumentCaptor.forClass(String.class);
		verify(objectWriter).put(key.capture(), any(byte[].class), eq("image/jpeg"));
		verify(objectWriter).delete(key.getValue());
	}

	@Test
	void closedCaseStillAllowsPhotoRemovalAfterCommit() {
		when(mapper.findByIdForUpdate(1L)).thenReturn(row(CaseStatus.CLOSED, "cases/1/photos/old.jpg"));

		service.delete(1L, 7L);
		verify(mapper).updatePhoto(1L, null);
		verify(objectWriter, never()).delete(anyString());

		TransactionSynchronizationManager.getSynchronizations()
				.forEach(TransactionSynchronization::afterCommit);
		verify(objectWriter).delete("cases/1/photos/old.jpg");
	}

	private MockMultipartFile jpeg() {
		return new MockMultipartFile(
				"photo", "photo.jpg", "image/jpeg",
				new byte[] {(byte) 0xff, (byte) 0xd8, (byte) 0xff, 0x01});
	}

	private MissingCaseRow row(CaseStatus status, String photoKey) {
		MissingCaseRow row = new MissingCaseRow();
		row.setId(1L);
		row.setStatus(status);
		row.setPhotoS3Key(photoKey);
		return row;
	}
}
