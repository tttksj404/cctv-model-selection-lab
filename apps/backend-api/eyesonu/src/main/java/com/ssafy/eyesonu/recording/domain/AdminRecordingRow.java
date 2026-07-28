package com.ssafy.eyesonu.recording.domain;

import java.time.Instant;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
public class AdminRecordingRow {

    private Long id;
    private Long cameraId;
    private String cameraCode;
    private String cameraName;
    private Instant startTime;
    private Instant endTime;
    private String s3Key;
    private Long fileSize;
    private Instant createdAt;
}
