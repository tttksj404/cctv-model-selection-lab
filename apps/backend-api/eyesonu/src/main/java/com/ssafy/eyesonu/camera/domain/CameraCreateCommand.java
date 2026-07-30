package com.ssafy.eyesonu.camera.domain;

import java.math.BigDecimal;

public class CameraCreateCommand {

    private Long id;
    private final Long mediaServerId;
    private final String cameraCode;
    private final String cameraName;
    private final BigDecimal latitude;
    private final BigDecimal longitude;
    private final String address;
    private final String rtspUrl;

    public CameraCreateCommand(
            Long mediaServerId,
            String cameraCode,
            String cameraName,
            BigDecimal latitude,
            BigDecimal longitude,
            String address,
            String rtspUrl) {
        this.mediaServerId = mediaServerId;
        this.cameraCode = cameraCode;
        this.cameraName = cameraName;
        this.latitude = latitude;
        this.longitude = longitude;
        this.address = address;
        this.rtspUrl = rtspUrl;
    }

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public Long getMediaServerId() {
        return mediaServerId;
    }

    public String getCameraCode() {
        return cameraCode;
    }

    public String getCameraName() {
        return cameraName;
    }

    public BigDecimal getLatitude() {
        return latitude;
    }

    public BigDecimal getLongitude() {
        return longitude;
    }

    public String getAddress() {
        return address;
    }

    public String getRtspUrl() {
        return rtspUrl;
    }
}
