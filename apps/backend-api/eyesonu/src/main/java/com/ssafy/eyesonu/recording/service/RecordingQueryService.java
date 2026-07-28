package com.ssafy.eyesonu.recording.service;

import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.recording.domain.AdminRecordingRow;
import com.ssafy.eyesonu.recording.domain.RecordingSortDirection;
import com.ssafy.eyesonu.recording.domain.RecordingSortField;
import com.ssafy.eyesonu.recording.dto.admin.AdminRecordingDetailResponse;
import com.ssafy.eyesonu.recording.dto.admin.AdminRecordingListResponse;
import com.ssafy.eyesonu.recording.dto.admin.AdminRecordingSearchCondition;
import com.ssafy.eyesonu.recording.mapper.RecordingMapper;
import com.ssafy.eyesonu.storage.StorageObjectUnavailableException;
import com.ssafy.eyesonu.storage.StorageObjectUrlSigner;
import java.time.Instant;
import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;

@Service
public class RecordingQueryService {

    private final RecordingMapper recordingMapper;
    private final RecordingRequestValidator requestValidator;
    private final StorageObjectUrlSigner storageObjectUrlSigner;

    public RecordingQueryService(
            RecordingMapper recordingMapper,
            RecordingRequestValidator requestValidator,
            StorageObjectUrlSigner storageObjectUrlSigner) {
        this.recordingMapper = recordingMapper;
        this.requestValidator = requestValidator;
        this.storageObjectUrlSigner = storageObjectUrlSigner;
    }

    public AdminRecordingPageResult findAll(AdminRecordingSearchCondition condition) {
        validatePage(condition.page(), condition.size());
        ParsedSort sort = parseSort(condition.sort());
        Instant startFrom = requestValidator.normalizeQueryTime(condition.startFrom(), "startFrom");
        Instant startTo = requestValidator.normalizeQueryTime(condition.startTo(), "startTo");
        if (startFrom != null && startTo != null && !startFrom.isBefore(startTo)) {
            throw validationError("startFrom must be before startTo");
        }

        long totalElements = recordingMapper.countAdminRecordings(condition.cameraId(), startFrom, startTo);
        long offset = (long) condition.page() * condition.size();
        List<AdminRecordingListResponse> recordings = totalElements == 0
                ? List.of()
                : recordingMapper.findAdminPage(
                                condition.cameraId(),
                                startFrom,
                                startTo,
                                sort.field(),
                                sort.direction(),
                                condition.size(),
                                offset)
                        .stream()
                        .map(AdminRecordingListResponse::from)
                        .toList();

        long totalPagesLong = totalElements / condition.size()
                + (totalElements % condition.size() == 0 ? 0 : 1);
        int totalPages = (int) Math.min(Integer.MAX_VALUE, totalPagesLong);
        return new AdminRecordingPageResult(
                recordings,
                condition.page(),
                condition.size(),
                totalElements,
                totalPages,
                sort.externalValue());
    }

    public AdminRecordingDetailResponse findById(Long recordingId) {
        AdminRecordingRow recording = recordingMapper.findAdminDetail(recordingId);
        if (recording == null) {
            throw new ApiException(HttpStatus.NOT_FOUND, "RESOURCE_NOT_FOUND", "Recording was not found");
        }

        try {
            return AdminRecordingDetailResponse.from(
                    recording, storageObjectUrlSigner.createGetUrl(recording.getS3Key()));
        } catch (StorageObjectUnavailableException exception) {
            throw new ApiException(HttpStatus.SERVICE_UNAVAILABLE, "STORAGE_UNAVAILABLE",
                    "Video URL could not be created");
        }
    }

    private void validatePage(int page, int size) {
        if (page < 0) {
            throw validationError("page must be at least 0");
        }
        if (size < 1 || size > 100) {
            throw validationError("size must be between 1 and 100");
        }
    }

    private ParsedSort parseSort(String value) {
        if (value == null || value.isBlank()) {
            return new ParsedSort(RecordingSortField.START_TIME, RecordingSortDirection.DESC,
                    "startTime,desc");
        }
        String[] parts = value.split(",", -1);
        if (parts.length != 2) {
            throw validationError("sort must have the form {field},{direction}");
        }

        RecordingSortField field = switch (parts[0]) {
            case "startTime" -> RecordingSortField.START_TIME;
            case "createdAt" -> RecordingSortField.CREATED_AT;
            default -> throw validationError("sort field must be startTime or createdAt");
        };
        RecordingSortDirection direction = switch (parts[1]) {
            case "asc" -> RecordingSortDirection.ASC;
            case "desc" -> RecordingSortDirection.DESC;
            default -> throw validationError("sort direction must be asc or desc");
        };
        return new ParsedSort(field, direction, parts[0] + "," + parts[1]);
    }

    private ApiException validationError(String message) {
        return new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_ERROR", message);
    }

    private record ParsedSort(
            RecordingSortField field,
            RecordingSortDirection direction,
            String externalValue) {
    }
}
