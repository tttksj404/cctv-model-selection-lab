package com.ssafy.eyesonu.recording.service;

import com.ssafy.eyesonu.camera.domain.Camera;
import com.ssafy.eyesonu.camera.mapper.CameraMapper;
import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.recording.domain.Recording;
import com.ssafy.eyesonu.recording.domain.RecordingRegistration;
import com.ssafy.eyesonu.recording.mapper.RecordingMapper;
import java.util.Objects;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class RecordingRegistrationWriter {

    private final CameraMapper cameraMapper;
    private final RecordingMapper recordingMapper;

    public RecordingRegistrationWriter(CameraMapper cameraMapper, RecordingMapper recordingMapper) {
        this.cameraMapper = cameraMapper;
        this.recordingMapper = recordingMapper;
    }

    @Transactional
    public Recording create(long mediaServerId, NormalizedRecordingCreateRequest request, long fileSize) {
        Camera camera = cameraMapper.findByCameraCodeForUpdate(request.cameraCode())
                .orElseThrow(() -> new ApiException(
                        HttpStatus.NOT_FOUND, "RESOURCE_NOT_FOUND", "Camera was not found"));
        if (!Objects.equals(camera.mediaServerId(), mediaServerId)) {
            throw new ApiException(HttpStatus.FORBIDDEN, "ACCESS_DENIED",
                    "Camera does not belong to the authenticated media server");
        }

        Recording recording = new Recording(
                null,
                camera.id(),
                request.startTime(),
                request.endTime(),
                request.objectKey(),
                fileSize,
                null);
        recordingMapper.insert(recording);
        if (recording.getId() == null) {
            throw new IllegalStateException("Recording insert did not return a generated id");
        }

        recordingMapper.insertRegistration(new RecordingRegistration(
                mediaServerId,
                request.idempotencyKey(),
                request.requestFingerprint(),
                recording.getId(),
                null));

        Recording persisted = recordingMapper.findById(recording.getId());
        if (persisted == null) {
            throw new IllegalStateException("Created recording could not be reloaded");
        }
        return persisted;
    }
}
