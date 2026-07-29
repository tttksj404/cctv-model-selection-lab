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
public class Recording {

    private Long id;
    private Long cameraId;
    private Instant startTime;
    private Instant endTime;
    private String s3Key;
    private Long fileSize;
    private Instant createdAt;

}
