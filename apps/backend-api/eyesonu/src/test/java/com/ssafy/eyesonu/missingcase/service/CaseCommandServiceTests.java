package com.ssafy.eyesonu.missingcase.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.ssafy.eyesonu.audit.service.AuditService;
import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.missingcase.domain.CaseStatus;
import com.ssafy.eyesonu.missingcase.domain.MissingCaseRow;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseCloseRequest;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseCreateRequest;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseStatusUpdateRequest;
import com.ssafy.eyesonu.missingcase.mapper.MissingCaseMapper;
import java.time.Instant;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.dao.DuplicateKeyException;

class CaseCommandServiceTests {

	private MissingCaseMapper mapper;
	private AuditService auditService;
	private CaseRequestValidator validator;
	private CaseNumberGenerator caseNumberGenerator;
	private CaseRegistrationWriter registrationWriter;
	private CaseCommandService service;

	@BeforeEach
	void setUp() {
		mapper = mock(MissingCaseMapper.class);
		auditService = mock(AuditService.class);
		validator = mock(CaseRequestValidator.class);
		caseNumberGenerator = mock(CaseNumberGenerator.class);
		registrationWriter = mock(CaseRegistrationWriter.class);
		service = new CaseCommandService(
				mapper,
				validator,
				caseNumberGenerator,
				registrationWriter,
				auditService);
	}

	@Test
	void retriesAfterUniqueConstraintCollisionDuringCaseNumberAllocation() {
		CaseCreateRequest request = mock(CaseCreateRequest.class);
		MissingCaseRow normalized = row(CaseStatus.RECEIVED);
		when(validator.normalizeCreate(request)).thenReturn(normalized);
		when(caseNumberGenerator.generate()).thenReturn("EFU-FIRST", "EFU-SECOND");
		when(registrationWriter.write(normalized, 7L))
				.thenThrow(new DuplicateKeyException("Duplicate entry for key 'uk_cases_case_number'"))
				.thenAnswer(invocation -> {
					normalized.setId(2L);
					normalized.setCaseNumber("EFU-SECOND");
					normalized.setReportedAt(Instant.parse("2026-07-20T00:00:00Z"));
					return normalized;
				});

		assertEquals("EFU-SECOND", service.create(request, 7L).caseNumber());
		verify(registrationWriter, times(2)).write(normalized, 7L);
	}

	@Test
	void searchingRequiresConditionAndActiveCamera() {
		when(mapper.findByIdForUpdate(1L)).thenReturn(row(CaseStatus.RECEIVED));
		when(mapper.countSearchConditions(1L)).thenReturn(1L);
		when(mapper.countActiveCameras(1L)).thenReturn(0L);

		ApiException exception = assertThrows(ApiException.class, () -> service.updateStatus(
				1L, new CaseStatusUpdateRequest(CaseStatus.SEARCHING, "탐색 시작"), 7L));

		assertEquals("BUSINESS_RULE_VIOLATION", exception.getCode());
		verify(mapper, never()).updateStatus(any(), any(), any());
	}

	@Test
	void appliesDocumentedStatusTransitionAfterResourcesAreReady() {
		when(mapper.findByIdForUpdate(1L)).thenReturn(row(CaseStatus.RECEIVED));
		when(mapper.countSearchConditions(1L)).thenReturn(1L);
		when(mapper.countActiveCameras(1L)).thenReturn(1L);
		when(mapper.findById(1L)).thenReturn(row(CaseStatus.SEARCHING));

		assertEquals(CaseStatus.SEARCHING, service.updateStatus(
				1L, new CaseStatusUpdateRequest(CaseStatus.SEARCHING, "탐색 시작"), 7L).status());

		verify(mapper).updateStatus(1L, CaseStatus.SEARCHING, null);
	}

	@Test
	void normalCloseRejectsPendingWorkAndForceCloseCancelsJobs() {
		when(mapper.findByIdForUpdate(1L)).thenReturn(row(CaseStatus.SEARCHING));
		when(mapper.countPendingCandidates(1L)).thenReturn(2L);
		when(mapper.countActiveJobs(1L)).thenReturn(1L);

		ApiException conflict = assertThrows(ApiException.class, () -> service.close(
				1L, new CaseCloseRequest("종료", false), 7L));
		assertEquals("CASE_CLOSE_CONFLICT", conflict.getCode());

		when(mapper.cancelActiveJobs(1L)).thenReturn(1);
		when(mapper.findById(1L)).thenReturn(row(CaseStatus.CLOSED));
		assertEquals(CaseStatus.CLOSED, service.close(
				1L, new CaseCloseRequest("관리자 강제 종료", true), 7L).status());
		verify(mapper).cancelActiveJobs(1L);
		verify(mapper).updateStatus(eq(1L), eq(CaseStatus.CLOSED), any(Instant.class));
	}

	private MissingCaseRow row(CaseStatus status) {
		MissingCaseRow row = new MissingCaseRow();
		row.setId(1L);
		row.setCaseNumber("EFU-0123456789ABCDEFGHJKMNPQRS");
		row.setStatus(status);
		row.setUpdatedAt(Instant.parse("2026-07-20T00:00:00Z"));
		if (status == CaseStatus.CLOSED) row.setClosedAt(Instant.parse("2026-07-20T01:00:00Z"));
		return row;
	}
}
