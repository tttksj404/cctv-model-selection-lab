package com.ssafy.eyesonu.caseinquiry.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record CaseStatusInquiryRequest(
		@NotBlank @Size(max = 30) String caseNumber,
		@NotBlank @Size(max = 30) String phone) {
}
