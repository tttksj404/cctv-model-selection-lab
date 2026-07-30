package com.ssafy.eyesonu.missingcase.controller;

import com.ssafy.eyesonu.auth.security.AdminPrincipal;
import com.ssafy.eyesonu.common.api.ApiResponse;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseCameraRequest;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseCameraResponse;
import com.ssafy.eyesonu.missingcase.dto.admin.SearchConditionCreateRequest;
import com.ssafy.eyesonu.missingcase.dto.admin.SearchConditionResponse;
import com.ssafy.eyesonu.missingcase.dto.admin.SearchConditionUpdateRequest;
import com.ssafy.eyesonu.missingcase.service.CaseSearchSetupService;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Positive;
import java.net.URI;
import java.util.List;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@Validated
@RestController
@RequestMapping("/api/v1/admin/cases/{caseId}")
public class AdminCaseSearchController {

	private final CaseSearchSetupService service;

	public AdminCaseSearchController(CaseSearchSetupService service) {
		this.service = service;
	}

	@GetMapping("/search-conditions")
	public ResponseEntity<ApiResponse<List<SearchConditionResponse>>> findConditions(
			@PathVariable @Positive Long caseId) {
		return ResponseEntity.ok(ApiResponse.of(service.findConditions(caseId)));
	}

	@PostMapping("/search-conditions")
	public ResponseEntity<ApiResponse<SearchConditionResponse>> createCondition(
			@PathVariable @Positive Long caseId,
			@Valid @RequestBody SearchConditionCreateRequest request,
			@AuthenticationPrincipal AdminPrincipal principal) {
		SearchConditionResponse response = service.createCondition(caseId, request, principal.getAdminId());
		return ResponseEntity.created(URI.create("/api/v1/admin/cases/" + caseId
				+ "/search-conditions/" + response.id())).body(ApiResponse.of(response));
	}

	@GetMapping("/search-conditions/{conditionId}")
	public ResponseEntity<ApiResponse<SearchConditionResponse>> findCondition(
			@PathVariable @Positive Long caseId, @PathVariable @Positive Long conditionId) {
		return ResponseEntity.ok(ApiResponse.of(service.findCondition(caseId, conditionId)));
	}

	@PatchMapping("/search-conditions/{conditionId}")
	public ResponseEntity<ApiResponse<SearchConditionResponse>> updateCondition(
			@PathVariable @Positive Long caseId, @PathVariable @Positive Long conditionId,
			@Valid @RequestBody SearchConditionUpdateRequest request,
			@AuthenticationPrincipal AdminPrincipal principal) {
		return ResponseEntity.ok(ApiResponse.of(
				service.updateCondition(caseId, conditionId, request, principal.getAdminId())));
	}

	@PutMapping("/search-conditions/{conditionId}")
	public ResponseEntity<ApiResponse<SearchConditionResponse>> replaceCondition(
			@PathVariable @Positive Long caseId, @PathVariable @Positive Long conditionId,
			@Valid @RequestBody SearchConditionCreateRequest request,
			@AuthenticationPrincipal AdminPrincipal principal) {
		return ResponseEntity.ok(ApiResponse.of(
				service.replaceCondition(caseId, conditionId, request, principal.getAdminId())));
	}

	@DeleteMapping("/search-conditions/{conditionId}")
	public ResponseEntity<Void> deleteCondition(
			@PathVariable @Positive Long caseId, @PathVariable @Positive Long conditionId,
			@AuthenticationPrincipal AdminPrincipal principal) {
		service.deleteCondition(caseId, conditionId, principal.getAdminId());
		return ResponseEntity.noContent().build();
	}

	@GetMapping("/cameras")
	public ResponseEntity<ApiResponse<List<CaseCameraResponse>>> findCameras(
			@PathVariable @Positive Long caseId) {
		return ResponseEntity.ok(ApiResponse.of(service.findCameras(caseId)));
	}

	@PostMapping("/cameras")
	public ResponseEntity<ApiResponse<List<CaseCameraResponse>>> addCameras(
			@PathVariable @Positive Long caseId,
			@Valid @RequestBody CaseCameraRequest request,
			@AuthenticationPrincipal AdminPrincipal principal) {
		return ResponseEntity.ok(ApiResponse.of(service.addCameras(caseId, request, principal.getAdminId())));
	}

	@DeleteMapping("/cameras/{cameraId}")
	public ResponseEntity<Void> removeCamera(
			@PathVariable @Positive Long caseId, @PathVariable @Positive Long cameraId,
			@AuthenticationPrincipal AdminPrincipal principal) {
		service.removeCamera(caseId, cameraId, principal.getAdminId());
		return ResponseEntity.noContent().build();
	}
}
