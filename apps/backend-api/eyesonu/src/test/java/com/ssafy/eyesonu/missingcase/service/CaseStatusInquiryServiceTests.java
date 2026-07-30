package com.ssafy.eyesonu.missingcase.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.anyMap;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import com.ssafy.eyesonu.audit.service.AuditService;
import com.ssafy.eyesonu.auth.config.AuthProperties;
import com.ssafy.eyesonu.auth.ratelimit.AttemptRateLimiter;
import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.missingcase.domain.CaseStatus;
import com.ssafy.eyesonu.missingcase.domain.CaseStatusInquiryRow;
import com.ssafy.eyesonu.missingcase.dto.CaseStatusInquiryResponse;
import com.ssafy.eyesonu.missingcase.mapper.CaseStatusInquiryMapper;
import java.time.Instant;
import java.util.Map;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class CaseStatusInquiryServiceTests {

	private static final String CASE_NUMBER = "EFU-0123456789ABCDEFGHJKMNPQRS";
	private static final String IP_ADDRESS = "127.0.0.1";

	private CaseStatusInquiryMapper mapper;
	private AuditService auditService;
	private AttemptRateLimiter rateLimiter;
	private CaseStatusInquiryService service;

	@BeforeEach
	void setUp() {
		mapper = mock(CaseStatusInquiryMapper.class);
		auditService = mock(AuditService.class);
		AuthProperties properties = new AuthProperties();
		properties.setRateLimitKeySecret("case-inquiry-test-secret");
		rateLimiter = new AttemptRateLimiter(properties);
		service = new CaseStatusInquiryService(
				mapper, new PhoneNumberNormalizer(), rateLimiter, auditService);
	}

	@Test
	void successfulInquiryNormalizesInputAndAuditsSuccess() {
		Instant reportedAt = Instant.parse("2026-07-20T01:30:00Z");
		Instant updatedAt = Instant.parse("2026-07-20T02:20:00Z");
		when(mapper.findStatus(CASE_NUMBER, "01012345678")).thenReturn(Optional.of(
				new CaseStatusInquiryRow(2L, CASE_NUMBER, CaseStatus.SEARCHING,
						reportedAt, updatedAt, null)));

		CaseStatusInquiryResponse response = service.inquire(
				"  efu-0123456789abcdefghjkmnpqrs  ", "010-1234-5678", IP_ADDRESS);

		assertEquals(CASE_NUMBER, response.caseNumber());
		assertEquals(CaseStatus.SEARCHING, response.status());
		assertEquals(reportedAt, response.reportedAt());
		assertEquals(updatedAt, response.updatedAt());
		verify(mapper).findStatus(CASE_NUMBER, "01012345678");
		verify(auditService).recordRequired(
				eq("CASE_INQUIRY_SUCCESS"), isNull(), eq(2L), eq("CASE"), eq(2L),
				eq(Map.of("ipFingerprint", rateLimiter.fingerprint(IP_ADDRESS))));
	}

	@Test
	void missingInquiryRecordsFailureAndReturnsNotFound() {
		when(mapper.findStatus(CASE_NUMBER, "01012345678")).thenReturn(Optional.empty());

		ApiException exception = assertThrows(ApiException.class, () -> service.inquire(
				CASE_NUMBER, "01012345678", IP_ADDRESS));

		assertEquals("INQUIRY_NOT_FOUND", exception.getCode());
		assertEquals(404, exception.getStatus().value());
		verify(auditService).recordBestEffort(
				eq("CASE_INQUIRY_FAILURE"), isNull(), isNull(), eq("CASE"), isNull(), anyMap());
	}

	@Test
	void rateLimitedInquiryReturns429AndAuditsOnlyFirstLimitedAttempt() {
		for (int attempt = 0; attempt < 5; attempt++) {
			rateLimiter.recordFailure("case-inquiry", IP_ADDRESS, "01012345678");
		}

		ApiException first = assertThrows(ApiException.class, () -> service.inquire(
				CASE_NUMBER, "01012345678", IP_ADDRESS));
		ApiException second = assertThrows(ApiException.class, () -> service.inquire(
				CASE_NUMBER, "01012345678", IP_ADDRESS));

		assertEquals("RATE_LIMIT_EXCEEDED", first.getCode());
		assertEquals(429, first.getStatus().value());
		assertEquals("RATE_LIMIT_EXCEEDED", second.getCode());
		assertEquals(429, second.getStatus().value());
		verify(auditService, times(1)).recordBestEffort(
				eq("CASE_INQUIRY_RATE_LIMITED"), isNull(), isNull(), eq("CASE"), isNull(), anyMap());
		verifyNoInteractions(mapper);
	}
}
