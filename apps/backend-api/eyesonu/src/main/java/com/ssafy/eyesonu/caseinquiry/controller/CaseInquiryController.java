package com.ssafy.eyesonu.caseinquiry.controller;

import com.ssafy.eyesonu.caseinquiry.service.CaseInquiryService;
import com.ssafy.eyesonu.caseinquiry.controller.docs.CaseInquiryControllerDocs;
import com.ssafy.eyesonu.caseinquiry.dto.CaseStatusInquiryRequest;
import com.ssafy.eyesonu.caseinquiry.dto.CaseStatusInquiryResponse;
import com.ssafy.eyesonu.common.api.ApiResponse;
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
public class CaseInquiryController implements CaseInquiryControllerDocs {

	private final CaseInquiryService caseInquiryService;

	public CaseInquiryController(CaseInquiryService caseInquiryService) {
		this.caseInquiryService = caseInquiryService;
	}

	@PostMapping("/status-inquiries")
	@Override
	public ResponseEntity<ApiResponse<CaseStatusInquiryResponse>> inquire(
			@Valid @RequestBody CaseStatusInquiryRequest body,
			HttpServletRequest request) {
		CaseStatusInquiryResponse response = caseInquiryService.inquire(
				body.caseNumber(), body.phone(), request.getRemoteAddr());
		return ResponseEntity.ok()
				.cacheControl(CacheControl.noStore())
				.body(ApiResponse.of(response));
	}
}
