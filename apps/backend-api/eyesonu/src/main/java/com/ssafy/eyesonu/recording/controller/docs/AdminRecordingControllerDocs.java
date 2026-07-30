package com.ssafy.eyesonu.recording.controller.docs;

import com.ssafy.eyesonu.common.api.ApiErrorResponse;
import com.ssafy.eyesonu.common.api.ApiResponse;
import com.ssafy.eyesonu.common.api.PagedApiResponse;
import com.ssafy.eyesonu.common.config.SwaggerConfig;
import com.ssafy.eyesonu.recording.dto.admin.AdminRecordingDetailResponse;
import com.ssafy.eyesonu.recording.dto.admin.AdminRecordingListResponse;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.Positive;
import java.time.OffsetDateTime;
import java.util.List;
import org.springframework.http.ResponseEntity;

@Tag(name = "Admin recordings", description = "Search recording metadata and issue playback URLs")
public interface AdminRecordingControllerDocs {

    @Operation(
            summary = "Search recordings",
            description = "Returns a stable, database-paginated list. The time filter uses interval overlap.",
            security = @SecurityRequirement(name = SwaggerConfig.SESSION_SCHEME))
    @ApiResponses({
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "200", description = "Recordings returned", useReturnTypeSchema = true),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "400", description = "Invalid filter, page, size, or sort",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class)))
    })
    ResponseEntity<PagedApiResponse<List<AdminRecordingListResponse>>> findAll(
            @Parameter(description = "Camera id") @Positive Long cameraId,
            @Parameter(description = "Open interval start, with RFC 3339 offset and at most 6 fractional digits")
                    OffsetDateTime startFrom,
            @Parameter(description = "Open interval end, with RFC 3339 offset and at most 6 fractional digits")
                    OffsetDateTime startTo,
            @Parameter(description = "Zero-based page", example = "0") @Min(0) int page,
            @Parameter(description = "Page size from 1 through 100", example = "20") @Min(1) @Max(100) int size,
            @Parameter(
                    description = "Allowed field and direction pair",
                    example = "startTime,desc",
                    schema = @Schema(allowableValues = {
                            "startTime,asc", "startTime,desc", "createdAt,asc", "createdAt,desc"
                    }))
                    String sort);

    @Operation(
            summary = "Get recording detail",
            description = "Returns recording metadata and a short-lived playback URL.",
            security = @SecurityRequirement(name = SwaggerConfig.SESSION_SCHEME))
    @ApiResponses({
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "200", description = "Recording returned", useReturnTypeSchema = true),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "404", description = "Recording not found",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class))),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "503", description = "Playback URL could not be issued",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class)))
    })
    ResponseEntity<ApiResponse<AdminRecordingDetailResponse>> findById(
            @Parameter(description = "Recording id", required = true) @Positive Long recordingId);
}
