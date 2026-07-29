package com.ssafy.eyesonu.missingcase.service;

import com.ssafy.eyesonu.audit.service.AuditService;
import com.ssafy.eyesonu.auth.ratelimit.AttemptRateLimiter;
import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.missingcase.domain.CaseStatusInquiryRow;
import com.ssafy.eyesonu.missingcase.dto.CaseStatusInquiryResponse;
import com.ssafy.eyesonu.missingcase.mapper.CaseStatusInquiryMapper;
import java.util.Locale;
import java.util.Map;
import java.util.regex.Pattern;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;

@Service
public class CaseStatusInquiryService {

	private static final String RATE_LIMIT_SCOPE = "case-inquiry";
	private static final Pattern CASE_NUMBER = Pattern.compile("EFU-[0-9A-HJKMNP-TV-Z]{26}");

	private final CaseStatusInquiryMapper caseStatusInquiryMapper;
	private final PhoneNumberNormalizer phoneNumberNormalizer;
	private final AttemptRateLimiter rateLimiter;
	private final AuditService auditService;

	public CaseStatusInquiryService(
			CaseStatusInquiryMapper caseStatusInquiryMapper,
			PhoneNumberNormalizer phoneNumberNormalizer,
			AttemptRateLimiter rateLimiter,
			AuditService auditService) {
		this.caseStatusInquiryMapper = caseStatusInquiryMapper;
		this.phoneNumberNormalizer = phoneNumberNormalizer;
		this.rateLimiter = rateLimiter;
		this.auditService = auditService;
	}

	public CaseStatusInquiryResponse inquire(String rawCaseNumber, String rawPhone, String ipAddress) {
		String caseNumber = normalizeCaseNumber(rawCaseNumber);
		String phone = normalizePhone(rawPhone);
		validateCaseNumber(caseNumber);

		if (!rateLimiter.isAllowed(RATE_LIMIT_SCOPE, ipAddress, phone)) {
			auditLimited(ipAddress, phone);
			throw new ApiException(
					HttpStatus.TOO_MANY_REQUESTS,
					"RATE_LIMIT_EXCEEDED",
					"잠시 후 다시 시도해 주세요.");
		}

		CaseStatusInquiryRow row = caseStatusInquiryMapper.findStatus(caseNumber, phone).orElse(null);
		if (row == null) {
			rateLimiter.recordFailure(RATE_LIMIT_SCOPE, ipAddress, phone);
			auditService.recordBestEffort(
					"CASE_INQUIRY_FAILURE", null, null, "CASE", null,
					Map.of(
							"phoneFingerprint", rateLimiter.fingerprint(phone),
							"caseFingerprint", rateLimiter.fingerprint(caseNumber),
							"ipFingerprint", rateLimiter.fingerprint(ipAddress)));
			throw new ApiException(
					HttpStatus.NOT_FOUND, "INQUIRY_NOT_FOUND", "조회 가능한 사건이 없습니다.");
		}

		auditService.recordRequired(
				"CASE_INQUIRY_SUCCESS", null, row.id(), "CASE", row.id(),
				Map.of("ipFingerprint", rateLimiter.fingerprint(ipAddress)));
		rateLimiter.recordSuccess(RATE_LIMIT_SCOPE, ipAddress, phone);
		return new CaseStatusInquiryResponse(
				row.caseNumber(),
				row.status(),
				row.reportedAt(),
				row.updatedAt(),
				row.closedAt());
	}

	private void auditLimited(String ipAddress, String phone) {
		if (rateLimiter.shouldAuditLimited(RATE_LIMIT_SCOPE, ipAddress, phone)) {
			auditService.recordBestEffort(
					"CASE_INQUIRY_RATE_LIMITED", null, null, "CASE", null,
					Map.of(
							"phoneFingerprint", rateLimiter.fingerprint(phone),
							"ipFingerprint", rateLimiter.fingerprint(ipAddress)));
		}
	}

	private String normalizeCaseNumber(String value) {
		return value == null ? "" : value.trim().toUpperCase(Locale.ROOT);
	}

	private String normalizePhone(String value) {
		try {
			return phoneNumberNormalizer.normalize(value);
		}
		catch (IllegalArgumentException exception) {
			throw validationError();
		}
	}

	private void validateCaseNumber(String caseNumber) {
		if (!CASE_NUMBER.matcher(caseNumber).matches()) {
			throw validationError();
		}
	}

	private ApiException validationError() {
		return new ApiException(
				HttpStatus.BAD_REQUEST, "VALIDATION_ERROR", "조회 정보 형식이 올바르지 않습니다.");
	}
}
