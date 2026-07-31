package com.ssafy.eyesonu.missingcase.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.missingcase.domain.CaseSortDirection;
import com.ssafy.eyesonu.missingcase.domain.CaseSortField;
import com.ssafy.eyesonu.missingcase.domain.CaseStatus;
import com.ssafy.eyesonu.missingcase.domain.Gender;
import com.ssafy.eyesonu.missingcase.domain.MissingCaseRow;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseDetailResponse;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseSearchCondition;
import com.ssafy.eyesonu.missingcase.mapper.MissingCaseMapper;
import com.ssafy.eyesonu.storage.StorageObjectUrlSigner;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class CaseQueryServiceTests {

	private MissingCaseMapper mapper;
	private StorageObjectUrlSigner urlSigner;
	private CaseQueryService service;

	@BeforeEach
	void setUp() {
		mapper = mock(MissingCaseMapper.class);
		urlSigner = mock(StorageObjectUrlSigner.class);
		service = new CaseQueryService(mapper, urlSigner);
	}

	@Test
	void appliesFiltersPaginationSortAndSignedPhotoUrl() {
		Instant from = Instant.parse("2026-07-01T00:00:00Z");
		Instant to = Instant.parse("2026-08-01T00:00:00Z");
		MissingCaseRow row = row();
		when(mapper.countCases(CaseStatus.SEARCHING, row.getCaseNumber(), "민수", from, to))
				.thenReturn(21L);
		when(mapper.findPage(
				CaseStatus.SEARCHING, row.getCaseNumber(), "민수", from, to,
				CaseSortField.UPDATED_AT, CaseSortDirection.ASC, 10, 10L))
				.thenReturn(List.of(row));
		when(urlSigner.createGetUrl(row.getPhotoS3Key())).thenReturn("https://storage.example/photo");

		CasePageResult result = service.findAll(new CaseSearchCondition(
				CaseStatus.SEARCHING,
				"  efu-0123456789abcdefghjkmnpqrs  ",
				"  민수  ",
				OffsetDateTime.parse("2026-07-01T09:00:00+09:00"),
				OffsetDateTime.parse("2026-08-01T09:00:00+09:00"),
				1,
				10,
				"updatedAt,asc"));

		assertEquals(21L, result.totalElements());
		assertEquals(3, result.totalPages());
		assertEquals("https://storage.example/photo", result.cases().getFirst().photoUrl());
		verify(mapper).findPage(
				CaseStatus.SEARCHING, row.getCaseNumber(), "민수", from, to,
				CaseSortField.UPDATED_AT, CaseSortDirection.ASC, 10, 10L);
	}

	@Test
	void rejectsInvalidSortAndNonIncreasingPeriod() {
		ApiException invalidSort = assertThrows(ApiException.class, () -> service.findAll(new CaseSearchCondition(
				null, null, null, null, null, 0, 20, "status,desc")));
		assertApiError(invalidSort);

		ApiException invalidPeriod = assertThrows(ApiException.class, () -> service.findAll(new CaseSearchCondition(
				null, null, null,
				OffsetDateTime.parse("2026-08-01T00:00:00Z"),
				OffsetDateTime.parse("2026-08-01T00:00:00Z"),
				0, 20, "reportedAt,desc")));
		assertApiError(invalidPeriod);
	}

	@Test
	void acceptsInclusivePageSizeBoundaries() {
		when(mapper.countCases(null, null, null, null, null)).thenReturn(0L);

		CasePageResult firstPage = service.findAll(new CaseSearchCondition(
				null, null, null, null, null, 0, 1, "reportedAt,desc"));
		CasePageResult largestPage = service.findAll(new CaseSearchCondition(
				null, null, null, null, null, 3, 100, "reportedAt,desc"));

		assertEquals(0, firstPage.page());
		assertEquals(1, firstPage.size());
		assertEquals(3, largestPage.page());
		assertEquals(100, largestPage.size());
		verifyNoInteractions(urlSigner);
	}

	@Test
	void caseWithoutPhotoDoesNotRequestSignedUrl() {
		MissingCaseRow row = row();
		row.setPhotoS3Key(null);
		when(mapper.findById(1L)).thenReturn(row);

		CaseDetailResponse result = service.findById(1L);

		assertNull(result.photoUrl());
		verifyNoInteractions(urlSigner);
	}

	private void assertApiError(ApiException exception) {
		assertEquals("VALIDATION_ERROR", exception.getCode());
		assertEquals(400, exception.getStatus().value());
	}

	private MissingCaseRow row() {
		MissingCaseRow row = new MissingCaseRow();
		row.setId(1L);
		row.setCaseNumber("EFU-0123456789ABCDEFGHJKMNPQRS");
		row.setStatus(CaseStatus.SEARCHING);
		row.setMissingName("김민수");
		row.setGender(Gender.MALE);
		row.setBirthYear(2000);
		row.setPhotoS3Key("cases/1/photos/photo.jpg");
		row.setLastSeenTime(Instant.parse("2026-07-20T00:00:00Z"));
		row.setLastSeenAddress("서울 강남구");
		row.setReportedAt(Instant.parse("2026-07-20T01:00:00Z"));
		row.setUpdatedAt(Instant.parse("2026-07-20T02:00:00Z"));
		return row;
	}
}
