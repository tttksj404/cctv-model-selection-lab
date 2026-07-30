package com.ssafy.eyesonu.missingcase.controller;

import com.ssafy.eyesonu.common.api.ApiResponse;
import com.ssafy.eyesonu.missingcase.controller.docs.CaseStatusInquiryControllerDocs;
import com.ssafy.eyesonu.missingcase.dto.CaseStatusInquiryRequest;
import com.ssafy.eyesonu.missingcase.dto.CaseStatusInquiryResponse;
import com.ssafy.eyesonu.missingcase.service.CaseStatusInquiryService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import org.springframework.http.CacheControl;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/cases")
public class CaseStatusInquiryController implements CaseStatusInquiryControllerDocs {

	private final CaseStatusInquiryService caseStatusInquiryService;

	public CaseStatusInquiryController(CaseStatusInquiryService caseStatusInquiryService) {
		this.caseStatusInquiryService = caseStatusInquiryService;
	}

	@PostMapping("/status-inquiries")
	@Override
	public ResponseEntity<ApiResponse<CaseStatusInquiryResponse>> inquire(
			@Valid @RequestBody CaseStatusInquiryRequest body,
			HttpServletRequest request) {
		CaseStatusInquiryResponse response = caseStatusInquiryService.inquire(
				body.caseNumber(), body.phone(), request.getRemoteAddr());
		return ResponseEntity.ok()
				.cacheControl(CacheControl.noStore())
				.body(ApiResponse.of(response));
	}
}
