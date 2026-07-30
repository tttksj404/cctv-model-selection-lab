package com.ssafy.eyesonu.missingcase.service;

import com.ssafy.eyesonu.missingcase.dto.admin.AdminCandidateListResponse;
import java.util.List;

public record AdminCandidatePageResult(
        List<AdminCandidateListResponse> candidates,
        int page,
        int size,
        long totalElements,
        int totalPages,
        String sort) {
}
