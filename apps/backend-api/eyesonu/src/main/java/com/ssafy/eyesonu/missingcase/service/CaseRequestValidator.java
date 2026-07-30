package com.ssafy.eyesonu.missingcase.service;

import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.missingcase.domain.CaseStatus;
import com.ssafy.eyesonu.missingcase.domain.MissingCaseRow;
import com.ssafy.eyesonu.missingcase.dto.admin.AppearanceRequest;
import com.ssafy.eyesonu.missingcase.dto.admin.AppearanceUpdateRequest;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseCreateRequest;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseUpdateRequest;
import com.ssafy.eyesonu.missingcase.dto.admin.ReporterUpdateRequest;
import java.math.BigDecimal;
import java.time.Year;
import java.util.stream.Stream;
import java.util.regex.Pattern;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;

@Component
public class CaseRequestValidator {

	private static final Pattern EMAIL = Pattern.compile("^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$");
	private final PhoneNumberNormalizer phoneNumberNormalizer;

	public CaseRequestValidator(PhoneNumberNormalizer phoneNumberNormalizer) {
		this.phoneNumberNormalizer = phoneNumberNormalizer;
	}

	public MissingCaseRow normalizeCreate(CaseCreateRequest request) {
		validateBirthYear(request.birthYear());
		validateCoordinates(request.lastSeenLat(), request.lastSeenLng());
		AppearanceRequest appearance = request.appearance();
		MissingCaseRow row = new MissingCaseRow();
		row.setStatus(CaseStatus.RECEIVED);
		row.setReporterName(required(request.reporter().name(), 50, "reporter.name"));
		row.setReporterPhone(normalizePhone(request.reporter().phone()));
		row.setReporterEmail(email(request.reporter().email()));
		row.setReporterRelation(optional(request.reporter().relation(), 50, "reporter.relation"));
		row.setReportContent(required(request.reportContent(), 4000, "reportContent"));
		row.setMissingName(required(request.missingName(), 50, "missingName"));
		row.setGender(request.gender());
		row.setBirthYear(request.birthYear());
		row.setHair(optional(appearance.hair(), 255, "appearance.hair"));
		row.setFace(optional(appearance.face(), 255, "appearance.face"));
		row.setUpperClothing(optional(appearance.upperClothing(), 255, "appearance.upperClothing"));
		row.setLowerClothing(optional(appearance.lowerClothing(), 255, "appearance.lowerClothing"));
		row.setShoes(optional(appearance.shoes(), 255, "appearance.shoes"));
		row.setBelongings(optional(appearance.belongings(), 1000, "appearance.belongings"));
		row.setBodyType(optional(appearance.bodyType(), 255, "appearance.bodyType"));
		row.setDistinctiveFeatures(optional(
				appearance.distinctiveFeatures(), 2000, "appearance.distinctiveFeatures"));
		validateAppearance(row);
		row.setLastSeenTime(request.lastSeenTime().toInstant());
		row.setLastSeenLat(request.lastSeenLat());
		row.setLastSeenLng(request.lastSeenLng());
		row.setLastSeenAddress(required(request.lastSeenAddress(), 255, "lastSeenAddress"));
		return row;
	}

	public void applyUpdate(MissingCaseRow row, CaseUpdateRequest request) {
		if (request == null || !request.hasChanges()) {
			throw validation("수정할 필드를 하나 이상 제공해야 합니다.");
		}
		if (request.hasReporter()) {
			applyReporter(row, request.getReporter());
		}
		if (request.hasReportContent()) row.setReportContent(required(request.getReportContent(), 4000, "reportContent"));
		if (request.hasMissingName()) row.setMissingName(required(request.getMissingName(), 50, "missingName"));
		if (request.hasGender()) {
			if (request.getGender() == null) throw validation("gender는 null일 수 없습니다.");
			row.setGender(request.getGender());
		}
		if (request.hasBirthYear()) {
			validateBirthYear(request.getBirthYear());
			row.setBirthYear(request.getBirthYear());
		}
		if (request.hasAppearance()) applyAppearance(row, request.getAppearance());
		validateAppearance(row);
		if (request.hasLastSeenTime()) {
			if (request.getLastSeenTime() == null) throw validation("lastSeenTime은 null일 수 없습니다.");
			row.setLastSeenTime(request.getLastSeenTime().toInstant());
		}
		if (request.hasLastSeenLat()) row.setLastSeenLat(request.getLastSeenLat());
		if (request.hasLastSeenLng()) row.setLastSeenLng(request.getLastSeenLng());
		validateCoordinates(row.getLastSeenLat(), row.getLastSeenLng());
		if (request.hasLastSeenAddress()) {
			row.setLastSeenAddress(required(request.getLastSeenAddress(), 255, "lastSeenAddress"));
		}
	}

	private void applyAppearance(MissingCaseRow row, AppearanceUpdateRequest request) {
		if (request == null || !request.hasChanges()) {
			throw validation("appearance에는 수정할 필드가 필요합니다.");
		}
		if (request.hasHair()) row.setHair(optional(request.getHair(), 255, "appearance.hair"));
		if (request.hasFace()) row.setFace(optional(request.getFace(), 255, "appearance.face"));
		if (request.hasUpperClothing()) row.setUpperClothing(optional(
				request.getUpperClothing(), 255, "appearance.upperClothing"));
		if (request.hasLowerClothing()) row.setLowerClothing(optional(
				request.getLowerClothing(), 255, "appearance.lowerClothing"));
		if (request.hasShoes()) row.setShoes(optional(request.getShoes(), 255, "appearance.shoes"));
		if (request.hasBelongings()) row.setBelongings(optional(
				request.getBelongings(), 1000, "appearance.belongings"));
		if (request.hasBodyType()) row.setBodyType(optional(
				request.getBodyType(), 255, "appearance.bodyType"));
		if (request.hasDistinctiveFeatures()) row.setDistinctiveFeatures(optional(
				request.getDistinctiveFeatures(), 2000, "appearance.distinctiveFeatures"));
	}

	private void applyReporter(MissingCaseRow row, ReporterUpdateRequest request) {
		if (request == null || !request.hasChanges()) {
			throw validation("reporter에는 수정할 필드가 필요합니다.");
		}
		if (request.hasName()) row.setReporterName(required(request.getName(), 50, "reporter.name"));
		if (request.hasPhone()) row.setReporterPhone(normalizePhone(request.getPhone()));
		if (request.hasEmail()) row.setReporterEmail(email(request.getEmail()));
		if (request.hasRelation()) row.setReporterRelation(optional(request.getRelation(), 50, "reporter.relation"));
	}

	private void validateAppearance(MissingCaseRow row) {
		if (Stream.of(
				row.getHair(), row.getFace(), row.getUpperClothing(), row.getLowerClothing(),
				row.getShoes(), row.getBelongings(), row.getBodyType(), row.getDistinctiveFeatures())
				.allMatch(value -> value == null || value.isBlank())) {
			throw validation("인상착의 항목을 하나 이상 입력해야 합니다.");
		}
	}

	private void validateCoordinates(BigDecimal latitude, BigDecimal longitude) {
		if ((latitude == null) != (longitude == null)) {
			throw validation("lastSeenLat와 lastSeenLng는 함께 제공해야 합니다.");
		}
		if (latitude != null && (latitude.compareTo(BigDecimal.valueOf(-90)) < 0
				|| latitude.compareTo(BigDecimal.valueOf(90)) > 0)) {
			throw validation("lastSeenLat 범위가 올바르지 않습니다.");
		}
		if (longitude != null && (longitude.compareTo(BigDecimal.valueOf(-180)) < 0
				|| longitude.compareTo(BigDecimal.valueOf(180)) > 0)) {
			throw validation("lastSeenLng 범위가 올바르지 않습니다.");
		}
	}

	private void validateBirthYear(Integer value) {
		if (value != null && (value < 1900 || value > Year.now().getValue())) {
			throw validation("birthYear는 1900년부터 현재 연도 사이여야 합니다.");
		}
	}

	private String normalizePhone(String value) {
		try {
			return phoneNumberNormalizer.normalize(value);
		}
		catch (IllegalArgumentException exception) {
			throw validation("전화번호 형식이 올바르지 않습니다.");
		}
	}

	private String email(String value) {
		String normalized = optional(value, 100, "email");
		if (normalized != null && !EMAIL.matcher(normalized).matches()) {
			throw validation("이메일 형식이 올바르지 않습니다.");
		}
		return normalized;
	}

	private String required(String value, int max, String field) {
		String normalized = optional(value, max, field);
		if (normalized == null) throw validation(field + "은(는) 필수입니다.");
		return normalized;
	}

	private String optional(String value, int max, String field) {
		if (value == null) return null;
		String normalized = value.trim();
		if (normalized.isEmpty()) return null;
		if (normalized.length() > max) throw validation(field + " 길이가 너무 깁니다.");
		return normalized;
	}

	private ApiException validation(String message) {
		return new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_ERROR", message);
	}
}
