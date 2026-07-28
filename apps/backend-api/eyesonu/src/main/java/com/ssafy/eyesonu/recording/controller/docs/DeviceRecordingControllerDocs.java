package com.ssafy.eyesonu.recording.controller.docs;

import com.ssafy.eyesonu.auth.device.MediaServerPrincipal;
import com.ssafy.eyesonu.common.api.ApiErrorResponse;
import com.ssafy.eyesonu.common.api.ApiResponse;
import com.ssafy.eyesonu.common.config.SwaggerConfig;
import com.ssafy.eyesonu.recording.dto.device.RecordingCreateRequest;
import com.ssafy.eyesonu.recording.dto.device.RecordingCreateResponse;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.enums.ParameterIn;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.http.ResponseEntity;

@Tag(name = "Device recordings", description = "Register metadata after a media server uploads a recording")
public interface DeviceRecordingControllerDocs {

    @Operation(
            summary = "Register uploaded recording metadata",
            description = "Verifies the uploaded object and atomically registers its metadata.",
            security = @SecurityRequirement(name = SwaggerConfig.DEVICE_KEY_SCHEME))
    @ApiResponses({
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "201", description = "Recording created", useReturnTypeSchema = true),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "200", description = "Successful idempotent replay", useReturnTypeSchema = true),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "400", description = "Invalid request, time, key, or idempotency key",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class))),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "401", description = "Device authentication required or invalid",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class))),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "403", description = "Camera belongs to another media server",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class))),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "404", description = "Camera not found",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class))),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "409", description = "Idempotency key conflict or duplicate object",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class))),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "413", description = "Storage object exceeds the configured size limit",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class))),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "415", description = "Content-Type is not application/json",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class))),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "422", description = "Storage object is missing or invalid",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class))),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "503", description = "Storage is unavailable",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class)))
    })
    ResponseEntity<ApiResponse<RecordingCreateResponse>> create(
            @Parameter(description = "Camera code", required = true) String cameraCode,
            @Parameter(
                    name = "Idempotency-Key",
                    description = "Canonical UUID scoped to the authenticated media server",
                    in = ParameterIn.HEADER,
                    required = true,
                    schema = @Schema(type = "string", format = "uuid",
                            example = "550e8400-e29b-41d4-a716-446655440000"))
                    String idempotencyKey,
            @Parameter(hidden = true) MediaServerPrincipal principal,
            @io.swagger.v3.oas.annotations.parameters.RequestBody(
                    description = "Uploaded recording metadata",
                    required = true,
                    content = @Content(schema = @Schema(implementation = RecordingCreateRequest.class)))
                    RecordingCreateRequest request);
}
