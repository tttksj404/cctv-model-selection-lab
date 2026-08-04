package com.ssafy.eyesonu.missingcase.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.anyCollection;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.lenient;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.ssafy.eyesonu.audit.service.AuditService;
import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.missingcase.domain.CaseStatus;
import com.ssafy.eyesonu.missingcase.domain.MissingCaseRow;
import com.ssafy.eyesonu.missingcase.domain.SearchConditionRow;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseCameraRequest;
import com.ssafy.eyesonu.missingcase.dto.admin.SearchConditionCreateRequest;
import com.ssafy.eyesonu.missingcase.dto.admin.SearchConditionResponse;
import com.ssafy.eyesonu.missingcase.dto.admin.SearchConditionUpdateRequest;
import com.ssafy.eyesonu.missingcase.mapper.MissingCaseMapper;
import com.ssafy.eyesonu.missingcase.messaging.SearchTargetEventPublisher;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Set;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class CaseSearchSetupServiceTests {

	private static final long CASE_ID = 178L;
	private static final long CONDITION_ID = 10L;
	private static final long ADMIN_ID = 1L;
	private static final String VALID_PROMPT =
			"a person wearing a black long sleeve top and blue pants";
	private static final String VALID_EXCLUSION_PROMPT =
			"a man wearing a white short sleeve top and gray pants";

	@Mock
	private MissingCaseMapper mapper;

	@Mock
	private CaseQueryService caseQueryService;

	@Mock
	private AuditService auditService;

	@Mock
	private SearchTargetEventPublisher searchTargetEventPublisher;

	private CaseSearchSetupService service;

	@BeforeEach
	void setUp() {
		service = new CaseSearchSetupService(
				mapper, caseQueryService, auditService, searchTargetEventPublisher,
				new RealtimePromptNormalizer());
		lenient().when(mapper.findByIdForUpdate(CASE_ID)).thenReturn(caseWithStatus(CaseStatus.RECEIVED));
	}

	@Test
	void putCanClearOptionalSearchSettings() {
		SearchConditionRow row = existingCondition();
		when(mapper.findSearchCondition(CASE_ID, CONDITION_ID)).thenReturn(row);
		when(mapper.countActiveJobsByCondition(CASE_ID, CONDITION_ID)).thenReturn(0L);

		service.replaceCondition(CASE_ID, CONDITION_ID,
				new SearchConditionCreateRequest(VALID_PROMPT, null, null, null, null), ADMIN_ID);

		assertNull(row.getExclusionPrompt());
		assertNull(row.getSearchStart());
		assertNull(row.getSearchEnd());
		assertNull(row.getSearchArea());
		verify(mapper).updateSearchCondition(row);
	}

	@Test
	void completedJobHistoryDoesNotBlockSoftDelete() {
		when(mapper.findSearchCondition(CASE_ID, CONDITION_ID)).thenReturn(existingCondition());
		when(mapper.countActiveJobsByCondition(CASE_ID, CONDITION_ID)).thenReturn(0L);

		service.deleteCondition(CASE_ID, CONDITION_ID, ADMIN_ID);

		verify(mapper).deleteSearchCondition(CASE_ID, CONDITION_ID);
	}

	@Test
	void cameraIdsAreSentToMapperAsOneBatch() {
		List<Long> cameraIds = List.of(1L, 2L, 3L);
		when(mapper.findExistingCameraIds(anyCollection())).thenReturn(cameraIds);
		when(mapper.findCaseCameras(CASE_ID)).thenReturn(List.of());

		service.addCameras(CASE_ID, new CaseCameraRequest(cameraIds), ADMIN_ID);

		verify(mapper).upsertCaseCameras(eq(CASE_ID), eq(Set.of(1L, 2L, 3L)));
	}

	@Test
	void searchingCaseSettingChangePublishesTargetUpdatedAfterCommit() {
		givenCaseStatus(CaseStatus.SEARCHING);
		when(mapper.findExistingCameraIds(anyCollection())).thenReturn(List.of(1L));
		when(mapper.findCaseCameras(CASE_ID)).thenReturn(List.of());

		service.addCameras(CASE_ID, new CaseCameraRequest(List.of(1L)), ADMIN_ID);

		verify(searchTargetEventPublisher).publishAfterCommit(
				eq(SearchTargetEventPublisher.TARGET_UPDATED), eq(CASE_ID), any(Instant.class));
	}

	@Test
	void createConditionIsRejectedForClosedCase() {
		givenCaseStatus(CaseStatus.CLOSED);

		assertThrows(ApiException.class, () -> service.createCondition(CASE_ID,
				new SearchConditionCreateRequest(VALID_PROMPT, null, null, null, null), ADMIN_ID));

		verify(mapper, never()).insertSearchCondition(org.mockito.ArgumentMatchers.any());
	}

	@Test
	void updateConditionIsRejectedForClosedCase() {
		givenCaseStatus(CaseStatus.CLOSED);

		assertThrows(ApiException.class, () -> service.updateCondition(CASE_ID, CONDITION_ID,
				new SearchConditionUpdateRequest(VALID_PROMPT, null, null, null, null), ADMIN_ID));

		verify(mapper, never()).findSearchCondition(CASE_ID, CONDITION_ID);
	}

	@Test
	void deleteConditionIsRejectedForClosedCase() {
		givenCaseStatus(CaseStatus.CLOSED);

		assertThrows(ApiException.class, () -> service.deleteCondition(CASE_ID, CONDITION_ID, ADMIN_ID));

		verify(mapper, never()).deleteSearchCondition(CASE_ID, CONDITION_ID);
	}

	@Test
	void updateConditionIsRejectedWhenAnActiveJobExists() {
		when(mapper.findSearchCondition(CASE_ID, CONDITION_ID)).thenReturn(existingCondition());
		when(mapper.countActiveJobsByCondition(CASE_ID, CONDITION_ID)).thenReturn(1L);

		assertThrows(ApiException.class, () -> service.updateCondition(CASE_ID, CONDITION_ID,
				new SearchConditionUpdateRequest(VALID_PROMPT, null, null, null, null), ADMIN_ID));

		verify(mapper, never()).updateSearchCondition(org.mockito.ArgumentMatchers.any());
	}

	@Test
	void deleteConditionIsRejectedWhenAnActiveJobExists() {
		when(mapper.findSearchCondition(CASE_ID, CONDITION_ID)).thenReturn(existingCondition());
		when(mapper.countActiveJobsByCondition(CASE_ID, CONDITION_ID)).thenReturn(1L);

		assertThrows(ApiException.class, () -> service.deleteCondition(CASE_ID, CONDITION_ID, ADMIN_ID));

		verify(mapper, never()).deleteSearchCondition(CASE_ID, CONDITION_ID);
	}

	@Test
	void invalidMainPromptReturnsDedicatedBadRequestCode() {
		when(mapper.findSearchCondition(CASE_ID, CONDITION_ID)).thenReturn(existingCondition());
		when(mapper.countActiveJobsByCondition(CASE_ID, CONDITION_ID)).thenReturn(0L);

		ApiException exception = assertThrows(ApiException.class, () -> service.updateCondition(
				CASE_ID, CONDITION_ID,
				new SearchConditionUpdateRequest(
						"a person wearing a khaki windbreaker", null, null, null, null),
				ADMIN_ID));

		assertApiError(exception, "REALTIME_PROMPT_INVALID", 400);
		verify(mapper, never()).updateSearchCondition(org.mockito.ArgumentMatchers.any());
	}

	@Test
	void invalidOptionalExclusionPromptReturnsDedicatedBadRequestCode() {
		ApiException exception = assertThrows(ApiException.class, () -> service.createCondition(
				CASE_ID,
				new SearchConditionCreateRequest(
						VALID_PROMPT, "exclude a khaki windbreaker", null, null, null),
				ADMIN_ID));

		assertApiError(exception, "REALTIME_PROMPT_INVALID", 400);
		verify(mapper, never()).insertSearchCondition(org.mockito.ArgumentMatchers.any());
	}

	@Test
	void createConditionRejectsEndBeforeStart() {
		assertThrows(ApiException.class, () -> service.createCondition(CASE_ID,
				new SearchConditionCreateRequest(VALID_PROMPT, null,
						OffsetDateTime.parse("2026-07-30T02:00:00+00:00"),
						OffsetDateTime.parse("2026-07-30T01:00:00+00:00"), null), ADMIN_ID));

		verify(mapper, never()).insertSearchCondition(org.mockito.ArgumentMatchers.any());
	}

	@Test
	void responseExposesCanonicalPromptsAndRealtimeUsability() {
		SearchConditionRow valid = existingCondition();
		SearchConditionRow invalid = existingCondition();
		invalid.setId(11L);
		invalid.setPrompt("a person wearing a khaki windbreaker");
		invalid.setExclusionPrompt(null);
		when(caseQueryService.require(CASE_ID)).thenReturn(caseWithStatus(CaseStatus.RECEIVED));
		when(mapper.findSearchConditions(CASE_ID)).thenReturn(List.of(valid, invalid));

		List<SearchConditionResponse> responses = service.findConditions(CASE_ID);

		assertEquals(VALID_PROMPT, responses.getFirst().normalizedPrompt());
		assertEquals(VALID_EXCLUSION_PROMPT, responses.getFirst().normalizedExclusionPrompt());
		assertTrue(responses.getFirst().realtimeUsable());
		assertNull(responses.get(1).normalizedPrompt());
		assertNull(responses.get(1).normalizedExclusionPrompt());
		assertFalse(responses.get(1).realtimeUsable());
	}

	@Test
	void searchingCaseCannotDeleteItsLastRealtimeUsableCondition() {
		givenCaseStatus(CaseStatus.SEARCHING);
		SearchConditionRow condition = existingCondition();
		when(mapper.findSearchCondition(CASE_ID, CONDITION_ID)).thenReturn(condition);
		when(mapper.countActiveJobsByCondition(CASE_ID, CONDITION_ID)).thenReturn(0L);
		when(mapper.findSearchConditions(CASE_ID)).thenReturn(List.of(condition));

		ApiException exception = assertThrows(
				ApiException.class, () -> service.deleteCondition(CASE_ID, CONDITION_ID, ADMIN_ID));

		assertApiError(exception, "BUSINESS_RULE_VIOLATION", 422);
		verify(mapper, never()).deleteSearchCondition(CASE_ID, CONDITION_ID);
	}

	@Test
	void searchingCaseCannotRemoveItsLastActiveCamera() {
		givenCaseStatus(CaseStatus.SEARCHING);
		when(mapper.existsActiveCaseCamera(CASE_ID, 1L)).thenReturn(true);
		when(mapper.countActiveCameras(CASE_ID)).thenReturn(1L);

		ApiException exception = assertThrows(
				ApiException.class, () -> service.removeCamera(CASE_ID, 1L, ADMIN_ID));

		assertApiError(exception, "BUSINESS_RULE_VIOLATION", 422);
		verify(mapper, never()).disableCaseCamera(CASE_ID, 1L);
	}

	@Test
	void addCamerasRejectsDuplicateCameraIds() {
		assertThrows(ApiException.class,
				() -> service.addCameras(CASE_ID, new CaseCameraRequest(List.of(1L, 1L)), ADMIN_ID));

		verify(mapper, never()).upsertCaseCameras(org.mockito.ArgumentMatchers.anyLong(),
				org.mockito.ArgumentMatchers.anySet());
	}

	private void givenCaseStatus(CaseStatus status) {
		when(mapper.findByIdForUpdate(CASE_ID)).thenReturn(caseWithStatus(status));
	}

	private MissingCaseRow caseWithStatus(CaseStatus status) {
		MissingCaseRow row = new MissingCaseRow();
		row.setId(CASE_ID);
		row.setStatus(status);
		return row;
	}

	private SearchConditionRow existingCondition() {
		SearchConditionRow row = new SearchConditionRow();
		row.setId(CONDITION_ID);
		row.setCaseId(CASE_ID);
		row.setPrompt(VALID_PROMPT);
		row.setExclusionPrompt(VALID_EXCLUSION_PROMPT);
		row.setSearchStart(Instant.parse("2026-07-30T00:00:00Z"));
		row.setSearchEnd(Instant.parse("2026-07-30T01:00:00Z"));
		row.setSearchArea("original area");
		return row;
	}

	private void assertApiError(ApiException exception, String code, int status) {
		assertEquals(code, exception.getCode());
		assertEquals(status, exception.getStatus().value());
	}
}
