package com.ssafy.eyesonu.recording.service;

import com.ssafy.eyesonu.camera.mapper.CameraMapper;
import com.ssafy.eyesonu.recording.domain.Recording;
import com.ssafy.eyesonu.recording.dto.RecordingCreateRequest;
import com.ssafy.eyesonu.recording.dto.RecordingUploadStatusUpdateRequest;
import com.ssafy.eyesonu.recording.mapper.RecordingMapper;
import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.storage.StorageObject;
import com.ssafy.eyesonu.storage.StorageObjectNotFoundException;
import com.ssafy.eyesonu.storage.StorageObjectUnavailableException;
import com.ssafy.eyesonu.storage.StorageObjectVerifier;
import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class RecordingService {
    private final RecordingMapper recordingMapper;
    private final CameraMapper cameraMapper;
    private final StorageObjectVerifier storageObjectVerifier;

    public RecordingService(RecordingMapper recordingMapper, CameraMapper cameraMapper,
            StorageObjectVerifier storageObjectVerifier) {
        this.recordingMapper = recordingMapper;
        this.cameraMapper = cameraMapper;
        this.storageObjectVerifier = storageObjectVerifier;
    }

    @Transactional
    public Recording create(String cameraCode, RecordingCreateRequest request) {
        Long cameraId = cameraMapper.findByCameraCode(cameraCode)
                .orElseThrow(() -> new ApiException(HttpStatus.NOT_FOUND, "CAMERA_NOT_FOUND", "Camera not found"))
                .id();
        if (request.endTime().isBefore(request.startTime())) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_ERROR", "endTime must not be before startTime");
        }
        if (request.objectKey() == null || request.objectKey().isBlank()
                || request.objectKey().startsWith("/")
                || request.objectKey().contains("\\")
                || request.objectKey().contains("..")) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "INVALID_OBJECT_KEY", "objectKey is invalid");
        }
        StorageObject object;
        try {
            object = storageObjectVerifier.stat(request.objectKey());
        } catch (StorageObjectNotFoundException exception) {
            throw new ApiException(HttpStatus.UNPROCESSABLE_ENTITY, "STORAGE_OBJECT_NOT_FOUND",
                    "Storage object was not found");
        } catch (StorageObjectUnavailableException exception) {
            throw new ApiException(HttpStatus.SERVICE_UNAVAILABLE, "STORAGE_UNAVAILABLE",
                    "Storage object could not be verified");
        }
        if (request.fileSize() != null && request.fileSize() != object.size()) {
            throw new ApiException(HttpStatus.UNPROCESSABLE_ENTITY, "STORAGE_SIZE_MISMATCH",
                    "Storage object size does not match fileSize");
        }
        Recording recording = new Recording(null, cameraId, request.startTime(), request.endTime(),
                request.objectKey(), object.size(), com.ssafy.eyesonu.recording.domain.UploadStatus.COMPLETED, null);
        recordingMapper.insert(recording);
        return recording;
    }

    public Recording get(Long recordingId) {
        Recording recording = recordingMapper.findById(recordingId);
        if (recording == null) {
            throw new ApiException(HttpStatus.NOT_FOUND, "RECORDING_NOT_FOUND", "Recording not found");
        }
        return recording;
    }

    public List<Recording> findAll(Long cameraId, com.ssafy.eyesonu.recording.domain.UploadStatus status,
            java.time.LocalDateTime startFrom, java.time.LocalDateTime startTo) {
        return recordingMapper.findAll(cameraId, status, startFrom, startTo);
    }

    @Transactional
    public Recording updateStatus(Long recordingId, RecordingUploadStatusUpdateRequest request) {
        get(recordingId);
        if (recordingMapper.updateUploadStatusAndFileSize(recordingId, request.uploadStatus(), request.fileSize()) != 1) {
            throw new ApiException(HttpStatus.NOT_FOUND, "RECORDING_NOT_FOUND", "Recording not found");
        }
        return get(recordingId);
    }
}
