package com.ssafy.eyesonu.missingcase.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertSame;
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
import com.ssafy.eyesonu.missingcase.domain.SearchConditionRow;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseCloseRequest;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseCreateRequest;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseStatusUpdateRequest;
import com.ssafy.eyesonu.missingcase.mapper.MissingCaseMapper;
import com.ssafy.eyesonu.missingcase.messaging.SearchTargetEventPublisher;
import java.time.Instant;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.dao.DuplicateKeyException;

class CaseCommandServiceTests {

	private MissingCaseMapper mapper;
	private AuditService auditService;
	private CaseRequestValidator validator;
	private CaseNumberGenerator caseNumberGenerator;
	private CaseRegistrationWriter registrationWriter;
	private SearchTargetEventPublisher searchTargetEventPublisher;
	private RealtimePromptNormalizer promptNormalizer;
	private CaseCommandService service;

	@BeforeEach
	void setUp() {
		mapper = mock(MissingCaseMapper.class);
		auditService = mock(AuditService.class);
		validator = mock(CaseRequestValidator.class);
		caseNumberGenerator = mock(CaseNumberGenerator.class);
		registrationWriter = mock(CaseRegistrationWriter.class);
		searchTargetEventPublisher = mock(SearchTargetEventPublisher.class);
		promptNormalizer = new RealtimePromptNormalizer();
		service = new CaseCommandService(
				mapper,
				validator,
				caseNumberGenerator,
				registrationWriter,
				auditService,
				searchTargetEventPublisher,
				promptNormalizer);
	}

	@Test
	void retriesAfterUniqueConstraintCollisionDuringCaseNumberAllocation() {
		CaseCreateRequest request = mock(CaseCreateRequest.class);
		MissingCaseRow normalized = row(CaseStatus.RECEIVED);
		when(validator.normalizeCreate(request)).thenReturn(normalized);
		when(caseNumberGenerator.generate()).thenReturn("EFU-FIRST", "EFU-SECOND");
		when(registrationWriter.write(normalized, 7L))
				.thenThrow(new CaseNumberCollisionException(new DuplicateKeyException("collision")))
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
	void returnsServiceUnavailableAfterAllCaseNumberAttemptsCollide() {
		CaseCreateRequest request = mock(CaseCreateRequest.class);
		MissingCaseRow normalized = row(CaseStatus.RECEIVED);
		when(validator.normalizeCreate(request)).thenReturn(normalized);
		when(caseNumberGenerator.generate()).thenReturn("EFU-COLLISION");
		when(registrationWriter.write(normalized, 7L))
				.thenThrow(new CaseNumberCollisionException(new DuplicateKeyException("collision")));

		ApiException exception = assertThrows(ApiException.class, () -> service.create(request, 7L));

		assertEquals(503, exception.getStatus().value());
		assertEquals("CASE_NUMBER_ALLOCATION_FAILED", exception.getCode());
		verify(registrationWriter, times(5)).write(normalized, 7L);
	}

	@Test
	void doesNotRetryUnclassifiedDuplicateKeyFailure() {
		CaseCreateRequest request = mock(CaseCreateRequest.class);
		MissingCaseRow normalized = row(CaseStatus.RECEIVED);
		DuplicateKeyException duplicate = new DuplicateKeyException("unrelated duplicate");
		when(validator.normalizeCreate(request)).thenReturn(normalized);
		when(caseNumberGenerator.generate()).thenReturn("EFU-FIRST");
		when(registrationWriter.write(normalized, 7L)).thenThrow(duplicate);

		DuplicateKeyException thrown = assertThrows(
				DuplicateKeyException.class, () -> service.create(request, 7L));

		assertSame(duplicate, thrown);
		verify(registrationWriter).write(normalized, 7L);
	}

	@Test
	void searchingRequiresConditionAndActiveCamera() {
		when(mapper.findByIdForUpdate(1L)).thenReturn(row(CaseStatus.RECEIVED));
		when(mapper.findSearchConditions(1L)).thenReturn(List.of(usableCondition()));
		when(mapper.countActiveCameras(1L)).thenReturn(0L);

		ApiException exception = assertThrows(ApiException.class, () -> service.updateStatus(
				1L, new CaseStatusUpdateRequest(CaseStatus.SEARCHING, "탐색 시작"), 7L));

		assertEquals("BUSINESS_RULE_VIOLATION", exception.getCode());
		assertEquals(422, exception.getStatus().value());
		verify(mapper, never()).updateStatus(any(), any(), any());
	}

	@Test
	void appliesDocumentedStatusTransitionAfterResourcesAreReady() {
		when(mapper.findByIdForUpdate(1L)).thenReturn(row(CaseStatus.RECEIVED));
		when(mapper.findSearchConditions(1L)).thenReturn(List.of(usableCondition()));
		when(mapper.countActiveCameras(1L)).thenReturn(1L);
		when(mapper.findById(1L)).thenReturn(row(CaseStatus.SEARCHING));

		assertEquals(CaseStatus.SEARCHING, service.updateStatus(
				1L, new CaseStatusUpdateRequest(CaseStatus.SEARCHING, "탐색 시작"), 7L).status());

		verify(mapper).updateStatus(1L, CaseStatus.SEARCHING, null);
		verify(searchTargetEventPublisher).publishAfterCommit(
				SearchTargetEventPublisher.TARGET_UPDATED, 1L, Instant.parse("2026-07-20T00:00:00Z"));
	}

	@Test
	void searchingRequiresAtLeastOneSearchCondition() {
		when(mapper.findByIdForUpdate(1L)).thenReturn(row(CaseStatus.RECEIVED));
		when(mapper.findSearchConditions(1L)).thenReturn(List.of());
		when(mapper.countActiveCameras(1L)).thenReturn(1L);

		ApiException exception = assertThrows(ApiException.class, () -> service.updateStatus(
				1L, new CaseStatusUpdateRequest(CaseStatus.SEARCHING, "search"), 7L));

		assertEquals("BUSINESS_RULE_VIOLATION", exception.getCode());
		assertEquals(422, exception.getStatus().value());
		verify(mapper, never()).updateStatus(any(), any(), any());
	}

	@Test
	void searchingRequiresARealtimeUsableCondition() {
		SearchConditionRow unusable = new SearchConditionRow();
		unusable.setPrompt("a person wearing a khaki windbreaker");
		when(mapper.findByIdForUpdate(1L)).thenReturn(row(CaseStatus.RECEIVED));
		when(mapper.findSearchConditions(1L)).thenReturn(List.of(unusable));

		ApiException exception = assertThrows(ApiException.class, () -> service.updateStatus(
				1L, new CaseStatusUpdateRequest(CaseStatus.SEARCHING, "search"), 7L));

		assertApiError(exception, "BUSINESS_RULE_VIOLATION", 422);
		verify(mapper, never()).updateStatus(any(), any(), any());
	}

	@Test
	void validatesReadinessForEveryTransitionBackIntoSearching() {
		for (CaseStatus previous : List.of(CaseStatus.CANDIDATE_FOUND, CaseStatus.FIELD_SEARCH)) {
			org.mockito.Mockito.reset(mapper, auditService, searchTargetEventPublisher);
			when(mapper.findByIdForUpdate(1L)).thenReturn(row(previous));
			when(mapper.findSearchConditions(1L)).thenReturn(List.of(usableCondition()));
			when(mapper.countActiveCameras(1L)).thenReturn(1L);
			when(mapper.findById(1L)).thenReturn(row(CaseStatus.SEARCHING));

			assertEquals(CaseStatus.SEARCHING, service.updateStatus(
					1L, new CaseStatusUpdateRequest(CaseStatus.SEARCHING, "resume"), 7L).status());
			verify(mapper).findSearchConditions(1L);
			verify(mapper).updateStatus(1L, CaseStatus.SEARCHING, null);
		}
	}

	@Test
	void rejectsDirectClosedStatusUpdate() {
		when(mapper.findByIdForUpdate(1L)).thenReturn(row(CaseStatus.RECEIVED));

		ApiException exception = assertThrows(ApiException.class, () -> service.updateStatus(
				1L, new CaseStatusUpdateRequest(CaseStatus.CLOSED, "closed"), 7L));

		assertEquals("VALIDATION_ERROR", exception.getCode());
		assertEquals(400, exception.getStatus().value());
		verify(mapper, never()).updateStatus(any(), any(), any());
	}

	@Test
	void rejectsUnsupportedStatusTransition() {
		when(mapper.findByIdForUpdate(1L)).thenReturn(row(CaseStatus.RECEIVED));

		ApiException exception = assertThrows(ApiException.class, () -> service.updateStatus(
				1L, new CaseStatusUpdateRequest(CaseStatus.FIELD_SEARCH, "field search"), 7L));

		assertEquals("BUSINESS_RULE_VIOLATION", exception.getCode());
		assertEquals(422, exception.getStatus().value());
		verify(mapper, never()).updateStatus(any(), any(), any());
	}

	@Test
	void normalCloseRejectsWhenOnlyPendingCandidatesExist() {
		when(mapper.findByIdForUpdate(1L)).thenReturn(row(CaseStatus.SEARCHING));
		when(mapper.countPendingCandidates(1L)).thenReturn(1L);
		when(mapper.countActiveJobs(1L)).thenReturn(0L);

		ApiException conflict = assertThrows(ApiException.class, () -> service.close(
				1L, new CaseCloseRequest("close", false), 7L));

		assertApiError(conflict, "CASE_CLOSE_CONFLICT", 409);
		verify(mapper, never()).cancelActiveJobs(1L);
		verify(mapper, never()).updateStatus(any(), any(), any());
	}

	@Test
	void normalCloseRejectsWhenOnlyActiveJobsExist() {
		when(mapper.findByIdForUpdate(1L)).thenReturn(row(CaseStatus.SEARCHING));
		when(mapper.countPendingCandidates(1L)).thenReturn(0L);
		when(mapper.countActiveJobs(1L)).thenReturn(1L);

		ApiException conflict = assertThrows(ApiException.class, () -> service.close(
				1L, new CaseCloseRequest("close", false), 7L));

		assertApiError(conflict, "CASE_CLOSE_CONFLICT", 409);
		verify(mapper, never()).cancelActiveJobs(1L);
		verify(mapper, never()).updateStatus(any(), any(), any());
	}

	@Test
	void normalCloseSucceedsWhenNoPendingWorkExists() {
		when(mapper.findByIdForUpdate(1L)).thenReturn(row(CaseStatus.SEARCHING));
		when(mapper.countPendingCandidates(1L)).thenReturn(0L);
		when(mapper.countActiveJobs(1L)).thenReturn(0L);
		when(mapper.findById(1L)).thenReturn(row(CaseStatus.CLOSED));

		assertEquals(CaseStatus.CLOSED, service.close(
				1L, new CaseCloseRequest("close", false), 7L).status());

		verify(mapper, never()).cancelActiveJobs(1L);
		verify(mapper).updateStatus(eq(1L), eq(CaseStatus.CLOSED), any(Instant.class));
		verify(searchTargetEventPublisher).publishAfterCommit(
				SearchTargetEventPublisher.TARGET_DISABLED, 1L, Instant.parse("2026-07-20T00:00:00Z"));
	}

	@Test
	void forceCloseCancelsActiveJobsEvenWhenPendingWorkExists() {
		when(mapper.findByIdForUpdate(1L)).thenReturn(row(CaseStatus.SEARCHING));
		when(mapper.countPendingCandidates(1L)).thenReturn(1L);
		when(mapper.countActiveJobs(1L)).thenReturn(1L);
		when(mapper.cancelActiveJobs(1L)).thenReturn(1);
		when(mapper.findById(1L)).thenReturn(row(CaseStatus.CLOSED));

		assertEquals(CaseStatus.CLOSED, service.close(
				1L, new CaseCloseRequest("force close", true), 7L).status());

		verify(mapper).cancelActiveJobs(1L);
		verify(mapper).updateStatus(eq(1L), eq(CaseStatus.CLOSED), any(Instant.class));
	}

	private void assertApiError(ApiException exception, String code, int status) {
		assertEquals(code, exception.getCode());
		assertEquals(status, exception.getStatus().value());
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

	private SearchConditionRow usableCondition() {
		SearchConditionRow row = new SearchConditionRow();
		row.setId(10L);
		row.setCaseId(1L);
		row.setPrompt("a person wearing a black long sleeve top and blue pants");
		return row;
	}
}
