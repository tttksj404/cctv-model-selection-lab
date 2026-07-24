package com.ssafy.eyesonu.caseinquiry.controller.docs;

import com.ssafy.eyesonu.caseinquiry.dto.CaseStatusInquiryRequest;
import com.ssafy.eyesonu.caseinquiry.dto.CaseStatusInquiryResponse;
import com.ssafy.eyesonu.common.api.ApiErrorResponse;
import com.ssafy.eyesonu.common.api.ApiResponse;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.ResponseEntity;

@Tag(name = "사건 조회", description = "신고자의 사건 진행 상황 조회 API")
public interface CaseInquiryControllerDocs {

	@Operation(
			summary = "사건 진행 상황 조회",
			description = "사건조회번호와 신고 전화번호가 모두 일치할 때 최소 진행 정보만 반환합니다.")
	@ApiResponses({
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "200", description = "사건 진행 상황 조회 성공", useReturnTypeSchema = true,
					content = @Content(mediaType = "application/json")),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "400", description = "조회 정보 형식 또는 요청 값 검증 실패",
					content = @Content(
							mediaType = "application/json",
							schema = @Schema(implementation = ApiErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "404", description = "일치하는 사건 없음",
					content = @Content(
							mediaType = "application/json",
							schema = @Schema(implementation = ApiErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "429", description = "조회 시도 횟수 초과",
					content = @Content(
							mediaType = "application/json",
							schema = @Schema(implementation = ApiErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "503", description = "감사 로그 또는 데이터베이스 일시 장애",
					content = @Content(
							mediaType = "application/json",
							schema = @Schema(implementation = ApiErrorResponse.class)))
	})
	ResponseEntity<ApiResponse<CaseStatusInquiryResponse>> inquire(
			@io.swagger.v3.oas.annotations.parameters.RequestBody(
					description = "사건조회번호와 신고 전화번호",
					required = true,
					content = @Content(schema = @Schema(implementation = CaseStatusInquiryRequest.class)))
			CaseStatusInquiryRequest body,
			@Parameter(hidden = true) HttpServletRequest request);
}
