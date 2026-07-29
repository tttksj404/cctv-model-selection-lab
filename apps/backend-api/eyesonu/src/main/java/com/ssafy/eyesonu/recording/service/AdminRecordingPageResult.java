package com.ssafy.eyesonu.recording.service;

import com.ssafy.eyesonu.recording.dto.admin.AdminRecordingListResponse;
import java.util.List;

public record AdminRecordingPageResult(
        List<AdminRecordingListResponse> recordings,
        int page,
        int size,
        long totalElements,
        int totalPages,
        String sort) {
}
