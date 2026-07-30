package com.ssafy.eyesonu.missingcase.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;

import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.missingcase.domain.Gender;
import com.ssafy.eyesonu.missingcase.domain.MissingCaseRow;
import com.ssafy.eyesonu.missingcase.dto.admin.AppearanceRequest;
import com.ssafy.eyesonu.missingcase.dto.admin.AppearanceUpdateRequest;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseCreateRequest;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseUpdateRequest;
import com.ssafy.eyesonu.missingcase.dto.admin.ReporterRequest;
import com.ssafy.eyesonu.missingcase.dto.admin.ReporterUpdateRequest;
import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.time.Year;
import org.junit.jupiter.api.Test;

class CaseRequestValidatorTests {

	private final CaseRequestValidator validator =
			new CaseRequestValidator(new PhoneNumberNormalizer());

	@Test
	void normalizesAdminCreateRequestAndReporterPhone() {
		MissingCaseRow row = validator.normalizeCreate(validCreate());

		assertEquals("01012345678", row.getReporterPhone());
		assertEquals("검은 셔츠", row.getUpperClothing());
		assertEquals(2001, row.getBirthYear());
		assertEquals("서울 강남구", row.getLastSeenAddress());
	}

	@Test
	void rejectsMissingAppearanceAndUnpairedCoordinates() {
		CaseCreateRequest request = validCreate();
		ApiException missingAppearance = assertThrows(ApiException.class, () -> validator.normalizeCreate(new CaseCreateRequest(
				request.reporter(), request.reportContent(), request.missingName(), request.gender(),
				request.birthYear(), new AppearanceRequest(null, null, null, null, null, null, null, null),
				request.lastSeenTime(), request.lastSeenLat(), request.lastSeenLng(), request.lastSeenAddress())));
		assertApiError(missingAppearance);

		ApiException unpairedCoordinates = assertThrows(ApiException.class, () -> validator.normalizeCreate(new CaseCreateRequest(
				request.reporter(), request.reportContent(), request.missingName(), request.gender(),
				request.birthYear(), request.appearance(), request.lastSeenTime(),
				BigDecimal.ONE, null, request.lastSeenAddress())));
		assertApiError(unpairedCoordinates);
	}

	@Test
	void acceptsInclusiveBirthYearAndCoordinateBoundaries() {
		CaseCreateRequest request = validCreate();

		MissingCaseRow oldestAndSouthern = validator.normalizeCreate(new CaseCreateRequest(
				request.reporter(), request.reportContent(), request.missingName(), request.gender(),
				1900, request.appearance(), request.lastSeenTime(),
				BigDecimal.valueOf(-90), BigDecimal.valueOf(-180), request.lastSeenAddress()));
		MissingCaseRow currentAndNorthern = validator.normalizeCreate(new CaseCreateRequest(
				request.reporter(), request.reportContent(), request.missingName(), request.gender(),
				Year.now().getValue(), request.appearance(), request.lastSeenTime(),
				BigDecimal.valueOf(90), BigDecimal.valueOf(180), request.lastSeenAddress()));

		assertEquals(1900, oldestAndSouthern.getBirthYear());
		assertEquals(BigDecimal.valueOf(-90), oldestAndSouthern.getLastSeenLat());
		assertEquals(BigDecimal.valueOf(-180), oldestAndSouthern.getLastSeenLng());
		assertEquals(Year.now().getValue(), currentAndNorthern.getBirthYear());
		assertEquals(BigDecimal.valueOf(90), currentAndNorthern.getLastSeenLat());
		assertEquals(BigDecimal.valueOf(180), currentAndNorthern.getLastSeenLng());
	}

	@Test
	void patchDistinguishesOmittedFromExplicitNull() {
		MissingCaseRow row = validator.normalizeCreate(validCreate());
		row.setReporterId(1L);
		CaseUpdateRequest patch = new CaseUpdateRequest();
		patch.setBirthYear(null);
		AppearanceUpdateRequest appearance = new AppearanceUpdateRequest();
		appearance.setBelongings(null);
		patch.setAppearance(appearance);
		ReporterUpdateRequest reporter = new ReporterUpdateRequest();
		reporter.setPhone("010 9999 8888");
		patch.setReporter(reporter);

		validator.applyUpdate(row, patch);

		assertNull(row.getBirthYear());
		assertNull(row.getBelongings());
		assertEquals("01099998888", row.getReporterPhone());
		assertEquals("검은 셔츠", row.getUpperClothing());
	}

	private CaseCreateRequest validCreate() {
		return new CaseCreateRequest(
				new ReporterRequest("홍길동", "010-1234-5678", "reporter@example.com", "보호자"),
				"마지막 연락 이후 귀가하지 않았습니다.",
				"김민수",
				Gender.MALE,
				2001,
				new AppearanceRequest(null, null, "검은 셔츠", null, null, "백팩", null, null),
				OffsetDateTime.parse("2026-07-20T00:10:00+09:00"),
				null,
				null,
				"서울 강남구");
	}

	private void assertApiError(ApiException exception) {
		assertEquals("VALIDATION_ERROR", exception.getCode());
		assertEquals(400, exception.getStatus().value());
	}
}
