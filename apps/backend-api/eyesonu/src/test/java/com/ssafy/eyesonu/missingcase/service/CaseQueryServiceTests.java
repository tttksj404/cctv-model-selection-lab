package com.ssafy.eyesonu.missingcase.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.missingcase.domain.CaseSortDirection;
import com.ssafy.eyesonu.missingcase.domain.CaseSortField;
import com.ssafy.eyesonu.missingcase.domain.CaseStatus;
import com.ssafy.eyesonu.missingcase.domain.Gender;
import com.ssafy.eyesonu.missingcase.domain.MissingCaseRow;
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
		assertThrows(ApiException.class, () -> service.findAll(new CaseSearchCondition(
				null, null, null, null, null, 0, 20, "status,desc")));
		assertThrows(ApiException.class, () -> service.findAll(new CaseSearchCondition(
				null, null, null,
				OffsetDateTime.parse("2026-08-01T00:00:00Z"),
				OffsetDateTime.parse("2026-08-01T00:00:00Z"),
				0, 20, "reportedAt,desc")));
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
