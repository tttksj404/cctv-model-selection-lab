package com.ssafy.eyesonu.missingcase.controller.docs;

import com.ssafy.eyesonu.auth.security.AdminPrincipal;
import com.ssafy.eyesonu.common.api.ApiResponse;
import com.ssafy.eyesonu.common.api.PagedApiResponse;
import com.ssafy.eyesonu.missingcase.domain.CaseStatus;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseCloseRequest;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseCreateRequest;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseCreateResponse;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseDetailResponse;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseListResponse;
import com.ssafy.eyesonu.missingcase.dto.admin.CasePhotoResponse;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseStateResponse;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseStatusUpdateRequest;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseUpdateRequest;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.Positive;
import java.time.OffsetDateTime;
import java.util.List;
import org.springframework.http.ResponseEntity;
import org.springframework.web.multipart.MultipartFile;

@Tag(name = "관리자 사건", description = "관리자 전용 사건 등록·조회·수정·상태 관리 API")
public interface AdminCaseControllerDocs {

	@Operation(summary = "사건 등록", description = "관리자가 신고자 스냅샷과 실종 사건을 등록합니다.")
	ResponseEntity<ApiResponse<CaseCreateResponse>> create(
			@Valid CaseCreateRequest body, @Parameter(hidden = true) AdminPrincipal principal);

	@Operation(summary = "사건 목록 조회")
	ResponseEntity<PagedApiResponse<List<CaseListResponse>>> findAll(
			CaseStatus status, String caseNumber, String missingName,
			OffsetDateTime reportedFrom, OffsetDateTime reportedTo,
			@Min(0) int page, @Min(1) @Max(100) int size, String sort);

	@Operation(summary = "사건 상세 조회")
	ResponseEntity<ApiResponse<CaseDetailResponse>> findById(@Positive Long caseId);

	@Operation(summary = "사건 정보 수정")
	ResponseEntity<ApiResponse<CaseDetailResponse>> update(
			@Positive Long caseId, CaseUpdateRequest body, @Parameter(hidden = true) AdminPrincipal principal);

	@Operation(summary = "실종자 사진 등록 또는 교체")
	ResponseEntity<ApiResponse<CasePhotoResponse>> putPhoto(
			@Positive Long caseId, MultipartFile photo, @Parameter(hidden = true) AdminPrincipal principal);

	@Operation(summary = "실종자 사진 제거")
	ResponseEntity<Void> deletePhoto(@Positive Long caseId, @Parameter(hidden = true) AdminPrincipal principal);

	@Operation(summary = "사건 상태 변경")
	ResponseEntity<ApiResponse<CaseStateResponse>> updateStatus(
			@Positive Long caseId, @Valid CaseStatusUpdateRequest body,
			@Parameter(hidden = true) AdminPrincipal principal);

	@Operation(summary = "사건 종료")
	ResponseEntity<ApiResponse<CaseStateResponse>> close(
			@Positive Long caseId, @Valid CaseCloseRequest body,
			@Parameter(hidden = true) AdminPrincipal principal);
}
