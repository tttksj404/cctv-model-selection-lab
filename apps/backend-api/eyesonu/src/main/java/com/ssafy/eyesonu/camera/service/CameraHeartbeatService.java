package com.ssafy.eyesonu.camera.service;

import com.ssafy.eyesonu.auth.device.MediaServerPrincipal;
import com.ssafy.eyesonu.camera.domain.CameraHeartbeatState;
import com.ssafy.eyesonu.camera.dto.device.CameraHeartbeatRequest;
import com.ssafy.eyesonu.camera.mapper.CameraMapper;
import com.ssafy.eyesonu.common.exception.ApiException;
import java.time.Instant;
import java.util.Locale;
import java.util.Objects;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.dao.DataAccessException;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class CameraHeartbeatService {

    private static final Logger log = LoggerFactory.getLogger(CameraHeartbeatService.class);
    private static final String ONLINE = "ONLINE";
    private static final String OFFLINE = "OFFLINE";
    private static final String ERROR = "ERROR";

    private final CameraMapper cameraMapper;

    public CameraHeartbeatService(CameraMapper cameraMapper) {
        this.cameraMapper = cameraMapper;
    }

    @Transactional
    public void receive(
            MediaServerPrincipal principal,
            String cameraCode,
            CameraHeartbeatRequest request) {
        if (principal == null || principal.mediaServerId() == null) {
            throw new ApiException(
                    HttpStatus.UNAUTHORIZED, "AUTHENTICATION_REQUIRED", "Authentication is required");
        }
        if (request == null || request.occurredAt() == null) {
            throw validation("occurredAt is required");
        }

        String normalizedCameraCode = normalizeCameraCode(cameraCode);
        String normalizedStatus = normalizeStatus(request.status());
        Instant occurredAt = request.occurredAt().toInstant();
        CameraHeartbeatState current;
        try {
            current = cameraMapper.findHeartbeatStateByCameraCodeForUpdate(normalizedCameraCode)
                    .orElseThrow(() -> new ApiException(
                            HttpStatus.NOT_FOUND, "RESOURCE_NOT_FOUND", "Camera was not found"));

            if (!Objects.equals(current.mediaServerId(), principal.mediaServerId())) {
                throw new ApiException(
                        HttpStatus.FORBIDDEN,
                        "ACCESS_DENIED",
                        "Camera does not belong to the authenticated media server");
            }

            if (current.lastHeartbeat() != null
                    && !occurredAt.isAfter(current.lastHeartbeat())) {
                log.warn(
                        "Ignored stale camera heartbeat cameraId={} cameraCode={} mediaServerId={} status={} lastHeartbeat={}",
                        current.id(), current.cameraCode(), current.mediaServerId(),
                        normalizedStatus, current.lastHeartbeat());
                return;
            }

            if (cameraMapper.updateHeartbeat(current.id(), normalizedStatus, occurredAt) != 1) {
                log.error(
                        "Camera heartbeat database update failed cameraId={} cameraCode={} mediaServerId={} status={} lastHeartbeat={}",
                        current.id(), current.cameraCode(), current.mediaServerId(),
                        normalizedStatus, occurredAt);
                throw operationFailed();
            }

            logStateChange(current, normalizedStatus, occurredAt, request.detail());
        } catch (DataAccessException exception) {
            log.error(
                    "Camera heartbeat database processing failed cameraCode={} mediaServerId={}",
                    normalizedCameraCode, principal.mediaServerId(), exception);
            throw exception;
        }
    }

    @Transactional
    public int markOffline(Instant now, java.time.Duration timeout) {
        if (now == null || timeout == null || timeout.isNegative() || timeout.isZero()) {
            throw new IllegalArgumentException("now and timeout must be positive");
        }

        Instant threshold = now.minus(timeout);
        int changed = 0;
        try {
            for (CameraHeartbeatState candidate : cameraMapper.findOfflineCandidates(threshold)) {
                if (cameraMapper.markOffline(
                        candidate.id(), candidate.lastHeartbeat(), threshold) == 1) {
                    changed++;
                    log.info(
                            "Camera status changed cameraId={} cameraCode={} mediaServerId={} status={} lastHeartbeat={}",
                            candidate.id(), candidate.cameraCode(), candidate.mediaServerId(),
                            OFFLINE, candidate.lastHeartbeat());
                }
            }
            return changed;
        } catch (DataAccessException exception) {
            log.error("Camera offline status check database processing failed", exception);
            throw exception;
        }
    }

    private void logStateChange(
            CameraHeartbeatState current,
            String status,
            Instant lastHeartbeat,
            String detail) {
        if (Objects.equals(current.status(), status)) {
            return;
        }

        if (ERROR.equals(status)) {
            String safeDetail = sanitizeDetail(detail);
            if (safeDetail == null) {
                log.warn(
                        "Camera status changed cameraId={} cameraCode={} mediaServerId={} status={} lastHeartbeat={}",
                        current.id(), current.cameraCode(), current.mediaServerId(), status, lastHeartbeat);
            } else {
                log.warn(
                        "Camera status changed cameraId={} cameraCode={} mediaServerId={} status={} lastHeartbeat={} detail={}",
                        current.id(), current.cameraCode(), current.mediaServerId(), status, lastHeartbeat,
                        safeDetail);
            }
            return;
        }

        log.info(
                "Camera status changed cameraId={} cameraCode={} mediaServerId={} status={} lastHeartbeat={}",
                current.id(), current.cameraCode(), current.mediaServerId(), status, lastHeartbeat);
    }

    private String normalizeCameraCode(String cameraCode) {
        if (cameraCode == null || cameraCode.isBlank()) {
            throw validation("cameraCode is required");
        }
        return cameraCode.trim();
    }

    private String normalizeStatus(String status) {
        String normalized = status == null ? null : status.trim().toUpperCase(Locale.ROOT);
        if (!ONLINE.equals(normalized) && !ERROR.equals(normalized)) {
            throw validation("Heartbeat status must be ONLINE or ERROR");
        }
        return normalized;
    }

    private String sanitizeDetail(String detail) {
        if (detail == null || detail.isBlank()) {
            return null;
        }
        return detail.codePoints()
                .limit(500)
                .mapToObj(codePoint -> Character.isISOControl(codePoint) ? " " : new String(Character.toChars(codePoint)))
                .reduce("", String::concat)
                .trim();
    }

    private ApiException validation(String message) {
        return new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_ERROR", message);
    }

    private ApiException operationFailed() {
        return new ApiException(
                HttpStatus.SERVICE_UNAVAILABLE,
                "CAMERA_HEARTBEAT_UPDATE_FAILED",
                "Camera heartbeat could not be updated");
    }
}
