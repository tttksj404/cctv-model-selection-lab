package com.ssafy.eyesonu.camera.domain;

import java.math.BigDecimal;
import java.time.Instant;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
public class CameraManagementRow {

    private Long id;
    private Long mediaServerId;
    private String mediaServerCode;
    private String mediaServerName;
    private String cameraCode;
    private String cameraName;
    private BigDecimal latitude;
    private BigDecimal longitude;
    private String address;
    private String rtspUrl;
    private String status;
    private Instant lastHeartbeat;
    private Instant createdAt;
    private Instant updatedAt;

    public Long id() {
        return id;
    }

    public Long mediaServerId() {
        return mediaServerId;
    }

    public String mediaServerCode() {
        return mediaServerCode;
    }

    public String mediaServerName() {
        return mediaServerName;
    }

    public String cameraCode() {
        return cameraCode;
    }

    public String cameraName() {
        return cameraName;
    }

    public BigDecimal latitude() {
        return latitude;
    }

    public BigDecimal longitude() {
        return longitude;
    }

    public String address() {
        return address;
    }

    public String rtspUrl() {
        return rtspUrl;
    }

    public String status() {
        return status;
    }

    public Instant lastHeartbeat() {
        return lastHeartbeat;
    }

    public Instant createdAt() {
        return createdAt;
    }

    public Instant updatedAt() {
        return updatedAt;
    }
}
