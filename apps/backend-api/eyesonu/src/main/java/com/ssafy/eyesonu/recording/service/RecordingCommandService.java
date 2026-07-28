package com.ssafy.eyesonu.recording.service;

import com.ssafy.eyesonu.recording.domain.Recording;
import com.ssafy.eyesonu.recording.dto.device.RecordingCreateRequest;
import com.ssafy.eyesonu.recording.dto.device.UploadStatusUpdateRequest;
import org.springframework.stereotype.Service;

@Service
public class RecordingCommandService {
    private final RecordingService recordingService;

    public RecordingCommandService(RecordingService recordingService) {
        this.recordingService = recordingService;
    }

    public Recording create(String cameraCode, RecordingCreateRequest request) {
        return recordingService.create(cameraCode, new com.ssafy.eyesonu.recording.dto.RecordingCreateRequest(
                request.startTime(), request.endTime(), request.objectKey(), request.fileSize(),
                com.ssafy.eyesonu.recording.domain.UploadStatus.COMPLETED));
    }

    public Recording updateStatus(Long recordingId, UploadStatusUpdateRequest request) {
        return recordingService.updateStatus(recordingId,
                new com.ssafy.eyesonu.recording.dto.RecordingUploadStatusUpdateRequest(request.uploadStatus(), request.fileSize()));
    }
}
