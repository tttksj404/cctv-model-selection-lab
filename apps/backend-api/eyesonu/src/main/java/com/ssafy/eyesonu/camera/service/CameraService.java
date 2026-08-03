package com.ssafy.eyesonu.camera.service;

import com.ssafy.eyesonu.audit.service.AuditService;
import com.ssafy.eyesonu.camera.domain.CameraCreateCommand;
import com.ssafy.eyesonu.camera.domain.CameraManagementRow;
import com.ssafy.eyesonu.camera.domain.CameraUpdateCommand;
import com.ssafy.eyesonu.camera.dto.CameraCreateRequest;
import com.ssafy.eyesonu.camera.dto.CameraDetailResponse;
import com.ssafy.eyesonu.camera.dto.CameraListResponse;
import com.ssafy.eyesonu.camera.dto.CameraNamePatchRequest;
import com.ssafy.eyesonu.camera.dto.CameraPutRequest;
import com.ssafy.eyesonu.camera.dto.CameraStreamUrlResponse;
import com.ssafy.eyesonu.camera.mapper.CameraMapper;
import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.mediaserver.mapper.MediaServerMapper;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class CameraService {

    private static final int MAX_SIZE = 100;
    private static final String DEFAULT_SORT = "createdAt,desc";

    private final CameraMapper cameraMapper;
    private final MediaServerMapper mediaServerMapper;
    private final AuditService auditService;

    public CameraService(
            CameraMapper cameraMapper,
            MediaServerMapper mediaServerMapper,
            AuditService auditService) {
        this.cameraMapper = cameraMapper;
        this.mediaServerMapper = mediaServerMapper;
        this.auditService = auditService;
    }

    public CameraPageResult findAdminPage(
            String status,
            String search,
            int page,
            int size,
            String sort) {
        validatePage(page, size);
        String normalizedStatus = normalizeStatus(status);
        String normalizedSearch = normalizeOptional(search);
        SortSpec sortSpec = parseSort(sort);
        long totalElements = cameraMapper.countAdminCameras(normalizedStatus, normalizedSearch);
        int totalPages = totalElements == 0 ? 0 : (int) ((totalElements + size - 1) / size);
        long offset = (long) page * size;
        List<CameraListResponse> cameras = cameraMapper.findAdminPage(
                        normalizedStatus,
                        normalizedSearch,
                        sortSpec.column(),
                        sortSpec.direction(),
                        size,
                        offset)
                .stream()
                .map(CameraListResponse::from)
                .toList();
        return new CameraPageResult(cameras, page, size, totalElements, totalPages, sortSpec.externalValue());
    }

    public CameraDetailResponse findAdminById(Long cameraId) {
        return toDetail(cameraMapper.findAdminById(cameraId));
    }

    public CameraStreamUrlResponse findStreamUrlById(Long cameraId) {
        return cameraMapper.findStreamUrlById(cameraId)
                .map(CameraStreamUrlResponse::new)
                .orElseThrow(() -> new ApiException(
                        HttpStatus.NOT_FOUND, "RESOURCE_NOT_FOUND", "Camera was not found."));
    }

    @Transactional
    public CameraDetailResponse create(Long adminId, CameraCreateRequest request) {
        String cameraCode = normalizeRequired(request.cameraCode());
        String cameraName = normalizeRequired(request.cameraName());
        String address = normalizeRequired(request.address());
        String rtspUrl = normalizeRequired(request.rtspUrl());
        ensureMediaServerExists(request.mediaServerId());

        CameraCreateCommand command = new CameraCreateCommand(
                request.mediaServerId(),
                cameraCode,
                cameraName,
                request.latitude(),
                request.longitude(),
                address,
                rtspUrl);
        try {
            if (cameraMapper.insert(command) != 1 || command.getId() == null) {
                throw operationFailed("CAMERA_CREATE_FAILED", "Camera could not be created.");
            }
        }
        catch (DuplicateKeyException exception) {
            throw duplicateCameraCode();
        }

        CameraManagementRow created = cameraMapper.findAdminById(command.getId());
        if (created == null) {
            throw operationFailed("CAMERA_CREATE_FAILED", "Created camera could not be loaded.");
        }
        auditService.recordRequired(
                "CAMERA_CREATED",
                adminId,
                null,
                "CAMERA",
                created.id(),
                Map.of(
                        "cameraCode", created.cameraCode(),
                        "cameraName", created.cameraName(),
                        "mediaServerId", created.mediaServerId(),
                        "status", created.status()));
        return CameraDetailResponse.from(created);
    }

    @Transactional
    public CameraDetailResponse patchName(Long adminId, Long cameraId, CameraNamePatchRequest request) {
        CameraManagementRow before = lockCamera(cameraId);
        String cameraName = normalizeRequired(request.cameraName());
        if (cameraMapper.updateName(cameraId, cameraName) != 1) {
            throw operationFailed("CAMERA_UPDATE_FAILED", "Camera name could not be updated.");
        }
        CameraManagementRow after = reloadCamera(cameraId);
        auditService.recordRequired(
                "CAMERA_NAME_UPDATED",
                adminId,
                null,
                "CAMERA",
                cameraId,
                Map.of("beforeName", before.cameraName(), "afterName", after.cameraName()));
        return CameraDetailResponse.from(after);
    }

    @Transactional
    public CameraDetailResponse replace(Long adminId, Long cameraId, CameraPutRequest request) {
        CameraManagementRow before = lockCamera(cameraId);
        ensureMediaServerExists(request.mediaServerId());
        CameraUpdateCommand command = new CameraUpdateCommand(
                cameraId,
                request.mediaServerId(),
                normalizeRequired(request.cameraName()),
                request.latitude(),
                request.longitude(),
                normalizeRequired(request.address()),
                normalizeRequired(request.rtspUrl()));
        if (cameraMapper.updateDetails(command) != 1) {
            throw operationFailed("CAMERA_UPDATE_FAILED", "Camera could not be updated.");
        }
        CameraManagementRow after = reloadCamera(cameraId);
        auditService.recordRequired(
                "CAMERA_UPDATED",
                adminId,
                null,
                "CAMERA",
                cameraId,
                Map.of(
                        "beforeMediaServerId", before.mediaServerId(),
                        "afterMediaServerId", after.mediaServerId(),
                        "beforeName", before.cameraName(),
                        "afterName", after.cameraName(),
                        "cameraCode", after.cameraCode()));
        return CameraDetailResponse.from(after);
    }

    private CameraManagementRow lockCamera(Long cameraId) {
        CameraManagementRow row = cameraMapper.findAdminByIdForUpdate(cameraId);
        if (row == null) {
            throw new ApiException(HttpStatus.NOT_FOUND, "RESOURCE_NOT_FOUND", "Camera was not found.");
        }
        return row;
    }

    private CameraManagementRow reloadCamera(Long cameraId) {
        CameraManagementRow row = cameraMapper.findAdminById(cameraId);
        if (row == null) {
            throw operationFailed("CAMERA_UPDATE_FAILED", "Updated camera could not be loaded.");
        }
        return row;
    }

    private CameraDetailResponse toDetail(CameraManagementRow row) {
        if (row == null) {
            throw new ApiException(HttpStatus.NOT_FOUND, "RESOURCE_NOT_FOUND", "Camera was not found.");
        }
        return CameraDetailResponse.from(row);
    }

    private void ensureMediaServerExists(Long mediaServerId) {
        if (mediaServerMapper.findById(mediaServerId).isEmpty()) {
            throw new ApiException(HttpStatus.NOT_FOUND, "RESOURCE_NOT_FOUND", "Media server was not found.");
        }
    }

    private void validatePage(int page, int size) {
        if (page < 0 || size < 1 || size > MAX_SIZE) {
            throw validation("Page must be non-negative and size must be between 1 and 100.");
        }
    }

    private String normalizeStatus(String status) {
        String normalized = normalizeOptional(status);
        if (normalized == null) {
            return null;
        }
        normalized = normalized.toUpperCase(Locale.ROOT);
        if (!List.of("ONLINE", "OFFLINE", "ERROR").contains(normalized)) {
            throw validation("Status must be ONLINE, OFFLINE, or ERROR.");
        }
        return normalized;
    }

    private SortSpec parseSort(String sort) {
        String value = normalizeOptional(sort);
        if (value == null) {
            value = DEFAULT_SORT;
        }
        String[] parts = value.split(",", -1);
        if (parts.length != 2) {
            throw validation("Sort must use the format field,direction.");
        }
        String field = parts[0].trim();
        String direction = parts[1].trim().toLowerCase(Locale.ROOT);
        String column = switch (field) {
            case "createdAt" -> "created_at";
            case "cameraName" -> "camera_name";
            case "cameraCode" -> "camera_code";
            default -> throw validation("Sort field is not supported.");
        };
        if (!direction.equals("asc") && !direction.equals("desc")) {
            throw validation("Sort direction must be asc or desc.");
        }
        return new SortSpec(column, direction.toUpperCase(Locale.ROOT), field + "," + direction);
    }

    private String normalizeRequired(String value) {
        String normalized = value == null ? null : value.trim();
        if (normalized == null || normalized.isEmpty()) {
            throw validation("Required text must not be blank.");
        }
        return normalized;
    }

    private String normalizeOptional(String value) {
        if (value == null) {
            return null;
        }
        String normalized = value.trim();
        return normalized.isEmpty() ? null : normalized;
    }

    private ApiException validation(String message) {
        return new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_ERROR", message);
    }

    private ApiException duplicateCameraCode() {
        return new ApiException(HttpStatus.CONFLICT, "DUPLICATE_RESOURCE", "Camera code already exists.");
    }

    private ApiException operationFailed(String code, String message) {
        return new ApiException(HttpStatus.SERVICE_UNAVAILABLE, code, message);
    }

    private record SortSpec(String column, String direction, String externalValue) {
    }
}
