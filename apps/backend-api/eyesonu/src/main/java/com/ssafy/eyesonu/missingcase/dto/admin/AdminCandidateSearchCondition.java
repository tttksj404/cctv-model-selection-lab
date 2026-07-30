package com.ssafy.eyesonu.missingcase.dto.admin;

import java.time.OffsetDateTime;

public record AdminCandidateSearchCondition(
        Long caseId,
        Long cameraId,
        String reviewStatus,
        OffsetDateTime detectedFrom,
        OffsetDateTime detectedTo,
        int page,
        int size,
        String sort) {
}
