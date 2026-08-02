package com.ssafy.eyesonu.missingcase.dto.admin;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

public record AdminCandidateReviewRequest(
        @NotBlank String reviewStatus,
        @Size(max = 2000) String reviewComment,
        @NotNull Long version) {
}
