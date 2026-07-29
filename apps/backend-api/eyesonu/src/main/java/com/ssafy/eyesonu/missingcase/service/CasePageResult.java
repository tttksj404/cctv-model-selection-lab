package com.ssafy.eyesonu.missingcase.service;

import com.ssafy.eyesonu.missingcase.dto.admin.CaseListResponse;
import java.util.List;

public record CasePageResult(
		List<CaseListResponse> cases,
		int page,
		int size,
		long totalElements,
		int totalPages,
		String sort) {
}
