package com.ssafy.eyesonu.missingcase.service;

import static org.junit.jupiter.api.Assertions.assertNull;
import static org.mockito.ArgumentMatchers.anyCollection;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.ssafy.eyesonu.audit.service.AuditService;
import com.ssafy.eyesonu.missingcase.domain.CaseStatus;
import com.ssafy.eyesonu.missingcase.domain.MissingCaseRow;
import com.ssafy.eyesonu.missingcase.domain.SearchConditionRow;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseCameraRequest;
import com.ssafy.eyesonu.missingcase.dto.admin.SearchConditionCreateRequest;
import com.ssafy.eyesonu.missingcase.mapper.MissingCaseMapper;
import java.math.BigDecimal;
import java.time.Instant;
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
