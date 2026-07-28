package com.ssafy.eyesonu.recording.service;

import com.ssafy.eyesonu.recording.domain.Recording;
import com.ssafy.eyesonu.recording.dto.admin.AdminRecordingSearchCondition;
import java.util.List;
import org.springframework.stereotype.Service;

@Service
public class RecordingQueryService {
    private final RecordingService recordingService;

    public RecordingQueryService(RecordingService recordingService) {
        this.recordingService = recordingService;
    }

    public List<Recording> findAll(AdminRecordingSearchCondition condition) {
        return recordingService.findAll(condition.cameraId(), condition.uploadStatus(), condition.startFrom(), condition.startTo());
    }

    public Recording findById(Long recordingId) {
        return recordingService.get(recordingId);
    }
}
