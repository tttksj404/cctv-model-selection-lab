package com.ssafy.eyesonu.missingcase.dto.admin;

import com.ssafy.eyesonu.missingcase.domain.CandidateSourceType;
import java.time.OffsetDateTime;

public record AdminCandidateSearchCondition(
        Long caseId,
        Long cameraId,
        CandidateSourceType sourceType,
        String reviewStatus,
        OffsetDateTime detectedFrom,
        OffsetDateTime detectedTo,
        int page,
        int size,
        String sort) {
}
