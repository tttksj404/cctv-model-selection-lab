package com.ssafy.eyesonu.missingcase.service;

import com.ssafy.eyesonu.missingcase.domain.MissingCaseRow;
import java.util.LinkedHashMap;
import java.util.Map;

final class CaseAuditValues {

	private CaseAuditValues() {
	}

	static Map<String, Object> snapshot(MissingCaseRow row) {
		Map<String, Object> value = new LinkedHashMap<>();
		value.put("caseNumber", row.getCaseNumber());
		value.put("status", row.getStatus());
		value.put("reporterName", row.getReporterName());
		value.put("reporterPhone", maskPhone(row.getReporterPhone()));
		value.put("reporterEmail", maskEmail(row.getReporterEmail()));
		value.put("reporterRelation", row.getReporterRelation());
		value.put("reportContent", row.getReportContent());
		value.put("missingName", row.getMissingName());
		value.put("gender", row.getGender());
		value.put("birthYear", row.getBirthYear());
		value.put("appearance", appearance(row));
		value.put("lastSeenTime", row.getLastSeenTime());
		value.put("lastSeenLat", row.getLastSeenLat());
		value.put("lastSeenLng", row.getLastSeenLng());
		value.put("lastSeenAddress", row.getLastSeenAddress());
		value.put("hasPhoto", row.getPhotoS3Key() != null);
		return value;
	}

	private static Map<String, Object> appearance(MissingCaseRow row) {
		Map<String, Object> value = new LinkedHashMap<>();
		value.put("hair", row.getHair());
		value.put("face", row.getFace());
		value.put("upperClothing", row.getUpperClothing());
		value.put("lowerClothing", row.getLowerClothing());
		value.put("shoes", row.getShoes());
		value.put("belongings", row.getBelongings());
		value.put("bodyType", row.getBodyType());
		value.put("distinctiveFeatures", row.getDistinctiveFeatures());
		return value;
	}

	private static String maskPhone(String phone) {
		if (phone == null || phone.length() < 4) return null;
		return "*******" + phone.substring(phone.length() - 4);
	}

	private static String maskEmail(String email) {
		if (email == null) return null;
		int separator = email.indexOf('@');
		return separator <= 0 ? "***" : email.substring(0, 1) + "***" + email.substring(separator);
	}
}
