package com.ssafy.eyesonu.missingcase.service;

import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.anyCollection;
import static org.mockito.ArgumentMatchers.eq;
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
import com.ssafy.eyesonu.missingcase.dto.admin.SearchConditionUpdateRequest;
import com.ssafy.eyesonu.missingcase.mapper.MissingCaseMapper;
import java.math.BigDecimal;
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

	@Mock
	private MissingCaseMapper mapper;

	@Mock
	private CaseQueryService caseQueryService;

	@Mock
	private AuditService auditService;

	private CaseSearchSetupService service;

	@BeforeEach
	void setUp() {
		service = new CaseSearchSetupService(mapper, caseQueryService, auditService);
		when(caseQueryService.require(CASE_ID)).thenReturn(openCase());
	}

	@Test
	void putCanClearOptionalSearchSettings() {
		SearchConditionRow row = existingCondition();
		when(mapper.findSearchCondition(CASE_ID, CONDITION_ID)).thenReturn(row);
		when(mapper.countActiveJobsByCondition(CASE_ID, CONDITION_ID)).thenReturn(0L);

		service.replaceCondition(CASE_ID, CONDITION_ID,
				new SearchConditionCreateRequest("updated prompt", null, null, null, null,
						new BigDecimal("0.80")), ADMIN_ID);

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
	void createConditionIsRejectedForClosedCase() {
		givenCaseStatus(CaseStatus.CLOSED);

		assertThrows(ApiException.class, () -> service.createCondition(CASE_ID,
				new SearchConditionCreateRequest("prompt", null, null, null, null,
						new BigDecimal("0.80")), ADMIN_ID));

		verify(mapper, never()).insertSearchCondition(org.mockito.ArgumentMatchers.any());
	}

	@Test
	void updateConditionIsRejectedForClosedCase() {
		givenCaseStatus(CaseStatus.CLOSED);

		assertThrows(ApiException.class, () -> service.updateCondition(CASE_ID, CONDITION_ID,
				new SearchConditionUpdateRequest("updated prompt", null, null, null, null,
						new BigDecimal("0.80")), ADMIN_ID));

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
				new SearchConditionUpdateRequest("updated prompt", null, null, null, null,
						new BigDecimal("0.80")), ADMIN_ID));

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
	void patchRejectsSimilarityThresholdOutsideTheAllowedRange() {
		when(mapper.findSearchCondition(CASE_ID, CONDITION_ID)).thenReturn(existingCondition());
		when(mapper.countActiveJobsByCondition(CASE_ID, CONDITION_ID)).thenReturn(0L);

		assertThrows(ApiException.class, () -> service.updateCondition(CASE_ID, CONDITION_ID,
				new SearchConditionUpdateRequest(null, null, null, null, null,
						new BigDecimal("1.01")), ADMIN_ID));

		verify(mapper, never()).updateSearchCondition(org.mockito.ArgumentMatchers.any());
	}

	@Test
	void createConditionRejectsEndBeforeStart() {
		assertThrows(ApiException.class, () -> service.createCondition(CASE_ID,
				new SearchConditionCreateRequest("prompt", null,
						OffsetDateTime.parse("2026-07-30T02:00:00+00:00"),
						OffsetDateTime.parse("2026-07-30T01:00:00+00:00"), null,
						new BigDecimal("0.80")), ADMIN_ID));

		verify(mapper, never()).insertSearchCondition(org.mockito.ArgumentMatchers.any());
	}

	@Test
	void addCamerasRejectsDuplicateCameraIds() {
		assertThrows(ApiException.class,
				() -> service.addCameras(CASE_ID, new CaseCameraRequest(List.of(1L, 1L)), ADMIN_ID));

		verify(mapper, never()).upsertCaseCameras(org.mockito.ArgumentMatchers.anyLong(),
				org.mockito.ArgumentMatchers.anySet());
	}

	private void givenCaseStatus(CaseStatus status) {
		MissingCaseRow row = openCase();
		row.setStatus(status);
		when(caseQueryService.require(CASE_ID)).thenReturn(row);
	}

	private MissingCaseRow openCase() {
		MissingCaseRow row = new MissingCaseRow();
		row.setId(CASE_ID);
		row.setStatus(CaseStatus.SEARCHING);
		return row;
	}

	private SearchConditionRow existingCondition() {
		SearchConditionRow row = new SearchConditionRow();
		row.setId(CONDITION_ID);
		row.setCaseId(CASE_ID);
		row.setPrompt("original prompt");
		row.setExclusionPrompt("original exclusion");
		row.setSearchStart(Instant.parse("2026-07-30T00:00:00Z"));
		row.setSearchEnd(Instant.parse("2026-07-30T01:00:00Z"));
		row.setSearchArea("original area");
		row.setSimilarityThreshold(new BigDecimal("0.70"));
		return row;
	}
}
