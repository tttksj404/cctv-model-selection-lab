package com.ssafy.eyesonu.missingcase.controller.docs;

import com.ssafy.eyesonu.auth.device.MediaServerPrincipal;
import com.ssafy.eyesonu.common.api.ApiErrorResponse;
import com.ssafy.eyesonu.common.api.ApiResponse;
import com.ssafy.eyesonu.common.config.SwaggerConfig;
import com.ssafy.eyesonu.missingcase.dto.device.CandidateEventUploadUrlCreateRequest;
import com.ssafy.eyesonu.missingcase.dto.device.CandidateEventUploadUrlCreateResponse;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.http.ResponseEntity;

@Tag(name = "Device candidate events", description = "Upload candidate images and register detection metadata")
public interface DeviceCandidateEventUploadControllerDocs {

    @Operation(
            summary = "Create candidate image upload URLs",
            description = "Creates short-lived MinIO/S3 PUT URLs and server-owned object keys for one frame and its crops.",
            security = @SecurityRequirement(name = SwaggerConfig.DEVICE_KEY_SCHEME))
    @ApiResponses({
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "201", description = "Upload URLs created", useReturnTypeSchema = true),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "400", description = "Invalid content type or duplicate track ID",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class))),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "401", description = "Device authentication required or invalid",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class))),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "403", description = "Camera belongs to another media server",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class))),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "404", description = "Case or camera not found",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class))),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "422", description = "Case is not searchable or camera is not selected",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class))),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "503", description = "Storage is unavailable",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class)))
    })
    ResponseEntity<ApiResponse<CandidateEventUploadUrlCreateResponse>> create(
            @Parameter(hidden = true) MediaServerPrincipal principal,
            @io.swagger.v3.oas.annotations.parameters.RequestBody(
                    description = "Candidate frame and crop upload request",
                    required = true,
                    content = @Content(schema = @Schema(implementation = CandidateEventUploadUrlCreateRequest.class)))
                    CandidateEventUploadUrlCreateRequest request);
}
