package com.ssafy.eyesonu.missingcase.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.anyMap;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import com.ssafy.eyesonu.audit.service.AuditService;
import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.missingcase.domain.CasePhotoState;
import com.ssafy.eyesonu.missingcase.domain.CaseStatus;
import com.ssafy.eyesonu.missingcase.mapper.MissingCaseMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class CasePhotoMetadataWriterTests {

	private MissingCaseMapper mapper;
	private AuditService auditService;
	private CasePhotoMetadataWriter writer;

	@BeforeEach
	void setUp() {
		mapper = mock(MissingCaseMapper.class);
		auditService = mock(AuditService.class);
		writer = new CasePhotoMetadataWriter(mapper, auditService);
	}

	@Test
	void replacementLocksUpdatesAndAuditsBeforeReturningPreviousKey() {
		when(mapper.findPhotoStateForUpdate(1L))
				.thenReturn(new CasePhotoState(1L, CaseStatus.SEARCHING, "old-key"));

		assertEquals("old-key", writer.replace(1L, "new-key", 7L));

		verify(mapper).updatePhoto(1L, "new-key");
		verify(auditService).recordRequired(
				eq("CASE_PHOTO_REPLACED"), eq(7L), eq(1L), eq("CASE"), eq(1L),
				anyMap(), anyMap(), anyMap());
	}

	@Test
	void finalLockedStateRejectsClosedCase() {
		when(mapper.findPhotoStateForUpdate(1L))
				.thenReturn(new CasePhotoState(1L, CaseStatus.CLOSED, "old-key"));

		ApiException exception = assertThrows(
				ApiException.class, () -> writer.replace(1L, "new-key", 7L));

		assertEquals("BUSINESS_RULE_VIOLATION", exception.getCode());
		verify(mapper, never()).updatePhoto(1L, "new-key");
		verifyNoInteractions(auditService);
	}

	@Test
	void removalIsAllowedForClosedCaseAndAudited() {
		when(mapper.findPhotoStateForUpdate(1L))
				.thenReturn(new CasePhotoState(1L, CaseStatus.CLOSED, "old-key"));

		assertEquals("old-key", writer.remove(1L, 7L));

		verify(mapper).updatePhoto(1L, null);
		verify(auditService).recordRequired(
				eq("CASE_PHOTO_DELETED"), eq(7L), eq(1L), eq("CASE"), eq(1L),
				anyMap(), anyMap(), anyMap());
	}

	@Test
	void removalWithoutPhotoIsNoOp() {
		when(mapper.findPhotoStateForUpdate(1L))
				.thenReturn(new CasePhotoState(1L, CaseStatus.CLOSED, null));

		assertNull(writer.remove(1L, 7L));

		verify(mapper, never()).updatePhoto(1L, null);
		verifyNoInteractions(auditService);
	}

	@Test
	void missingCaseReturnsNotFound() {
		when(mapper.findPhotoStateForUpdate(1L)).thenReturn(null);

		ApiException exception = assertThrows(
				ApiException.class, () -> writer.remove(1L, 7L));

		assertEquals("RESOURCE_NOT_FOUND", exception.getCode());
	}
}
