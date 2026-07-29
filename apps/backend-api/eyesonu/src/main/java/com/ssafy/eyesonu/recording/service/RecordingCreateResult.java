package com.ssafy.eyesonu.recording.service;

import com.ssafy.eyesonu.recording.domain.Recording;

public record RecordingCreateResult(Recording recording, boolean duplicate) {
}
