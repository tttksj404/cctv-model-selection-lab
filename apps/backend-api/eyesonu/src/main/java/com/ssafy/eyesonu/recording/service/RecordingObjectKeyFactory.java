package com.ssafy.eyesonu.recording.service;

import java.time.Instant;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.Locale;
import org.springframework.stereotype.Component;

@Component
public class RecordingObjectKeyFactory {

    private static final DateTimeFormatter START_TIME_FORMATTER = DateTimeFormatter
            .ofPattern("uuuu/MM/dd/uuuuMMdd'T'HHmmssSSSSSS'Z'", Locale.ROOT)
            .withZone(ZoneOffset.UTC);

    public String create(String cameraCode, Instant startTime, String idempotencyKey) {
        return "recordings/%s/%s_%s.mp4".formatted(
                cameraCode,
                START_TIME_FORMATTER.format(startTime),
                idempotencyKey);
    }
}
