package com.ssafy.eyesonu.recording.domain;

import java.time.LocalDateTime;
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
    private LocalDateTime startTime;
    private LocalDateTime endTime;
    private String s3Key;
    private Long fileSize;
    private UploadStatus uploadStatus;
    private LocalDateTime createdAt;

}
