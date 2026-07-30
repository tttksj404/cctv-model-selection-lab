package com.ssafy.eyesonu.missingcase.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

public record CaseStatusInquiryRequest(
		@NotBlank @Size(max = 30) String caseNumber,
		@NotBlank
		@Size(max = 30)
		@Pattern(regexp = "[0-9 -]+", message = "숫자, 하이픈, 공백만 사용할 수 있습니다.")
		String phone) {
}
