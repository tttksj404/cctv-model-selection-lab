package com.ssafy.eyesonu.missingcase.controller;

import com.ssafy.eyesonu.auth.security.AdminPrincipal;
import com.ssafy.eyesonu.common.api.ApiResponse;
import com.ssafy.eyesonu.common.api.PageMeta;
import com.ssafy.eyesonu.common.api.PagedApiResponse;
import com.ssafy.eyesonu.missingcase.controller.docs.AdminCaseControllerDocs;
import com.ssafy.eyesonu.missingcase.domain.CaseStatus;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseCloseRequest;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseCreateRequest;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseCreateResponse;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseDetailResponse;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseListResponse;
import com.ssafy.eyesonu.missingcase.dto.admin.CasePhotoResponse;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseSearchCondition;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseStateResponse;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseStatusUpdateRequest;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseUpdateRequest;
import com.ssafy.eyesonu.missingcase.service.CaseCommandService;
import com.ssafy.eyesonu.missingcase.service.CasePageResult;
import com.ssafy.eyesonu.missingcase.service.CasePhotoService;
import com.ssafy.eyesonu.missingcase.service.CaseQueryService;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.Positive;
import java.net.URI;
import java.time.OffsetDateTime;
import java.util.List;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RequestPart;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

@Validated
@RestController
@RequestMapping("/api/v1/admin/cases")
public class AdminCaseController implements AdminCaseControllerDocs {

	private final CaseCommandService commandService;
	private final CaseQueryService queryService;
	private final CasePhotoService photoService;

	public AdminCaseController(
			CaseCommandService commandService,
			CaseQueryService queryService,
			CasePhotoService photoService) {
		this.commandService = commandService;
		this.queryService = queryService;
		this.photoService = photoService;
	}

	@Override
	@PostMapping
	public ResponseEntity<ApiResponse<CaseCreateResponse>> create(
			@Valid @RequestBody CaseCreateRequest body,
			@AuthenticationPrincipal AdminPrincipal principal) {
		CaseCreateResponse created = commandService.create(body, principal.getAdminId());
		return ResponseEntity.created(URI.create("/api/v1/admin/cases/" + created.id()))
				.body(ApiResponse.of(created));
	}

	@Override
	@GetMapping
	public ResponseEntity<PagedApiResponse<List<CaseListResponse>>> findAll(
			@RequestParam(required = false) CaseStatus status,
			@RequestParam(required = false) String caseNumber,
			@RequestParam(required = false) String missingName,
			@RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME)
			OffsetDateTime reportedFrom,
			@RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME)
			OffsetDateTime reportedTo,
			@RequestParam(defaultValue = "0") @Min(0) int page,
			@RequestParam(defaultValue = "20") @Min(1) @Max(100) int size,
			@RequestParam(defaultValue = "reportedAt,desc") String sort) {
		CasePageResult result = queryService.findAll(new CaseSearchCondition(
				status, caseNumber, missingName, reportedFrom, reportedTo, page, size, sort));
		return ResponseEntity.ok(PagedApiResponse.of(
				result.cases(), new PageMeta(
						result.page(), result.size(), result.totalElements(), result.totalPages(), result.sort())));
	}

	@Override
	@GetMapping("/{caseId}")
	public ResponseEntity<ApiResponse<CaseDetailResponse>> findById(
			@PathVariable @Positive Long caseId) {
		return ResponseEntity.ok(ApiResponse.of(queryService.findById(caseId)));
	}

	@Override
	@PatchMapping("/{caseId}")
	public ResponseEntity<ApiResponse<CaseDetailResponse>> update(
			@PathVariable @Positive Long caseId,
			@RequestBody CaseUpdateRequest body,
			@AuthenticationPrincipal AdminPrincipal principal) {
		commandService.update(caseId, body, principal.getAdminId());
		return ResponseEntity.ok(ApiResponse.of(queryService.findById(caseId)));
	}

	@Override
	@PutMapping(path = "/{caseId}/photo", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
	public ResponseEntity<ApiResponse<CasePhotoResponse>> putPhoto(
			@PathVariable @Positive Long caseId,
			@RequestPart("photo") MultipartFile photo,
			@AuthenticationPrincipal AdminPrincipal principal) {
		return ResponseEntity.ok(ApiResponse.of(photoService.put(caseId, photo, principal.getAdminId())));
	}

	@Override
	@DeleteMapping("/{caseId}/photo")
	public ResponseEntity<Void> deletePhoto(
			@PathVariable @Positive Long caseId,
			@AuthenticationPrincipal AdminPrincipal principal) {
		photoService.delete(caseId, principal.getAdminId());
		return ResponseEntity.noContent().build();
	}

	@Override
	@PatchMapping("/{caseId}/status")
	public ResponseEntity<ApiResponse<CaseStateResponse>> updateStatus(
			@PathVariable @Positive Long caseId,
			@Valid @RequestBody CaseStatusUpdateRequest body,
			@AuthenticationPrincipal AdminPrincipal principal) {
		return ResponseEntity.ok(ApiResponse.of(
				commandService.updateStatus(caseId, body, principal.getAdminId())));
	}

	@Override
	@PostMapping("/{caseId}/close")
	public ResponseEntity<ApiResponse<CaseStateResponse>> close(
			@PathVariable @Positive Long caseId,
			@Valid @RequestBody CaseCloseRequest body,
			@AuthenticationPrincipal AdminPrincipal principal) {
		return ResponseEntity.ok(ApiResponse.of(commandService.close(caseId, body, principal.getAdminId())));
	}
}
