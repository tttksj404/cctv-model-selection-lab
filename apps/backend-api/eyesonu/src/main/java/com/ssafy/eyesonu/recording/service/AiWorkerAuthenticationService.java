package com.ssafy.eyesonu.recording.service;

import com.ssafy.eyesonu.common.config.properties.AiWorkerProperties;
import com.ssafy.eyesonu.common.exception.ApiException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;

@Service
public class AiWorkerAuthenticationService {

    private final AiWorkerProperties properties;

    public AiWorkerAuthenticationService(AiWorkerProperties properties) {
        this.properties = properties;
    }

    public void requireValidKey(String presentedKey) {
        byte[] expected = properties.getApiKey() == null
                ? new byte[0]
                : properties.getApiKey().getBytes(StandardCharsets.UTF_8);
        byte[] actual = presentedKey == null
                ? new byte[0]
                : presentedKey.getBytes(StandardCharsets.UTF_8);
        if (expected.length == 0 || !MessageDigest.isEqual(expected, actual)) {
            throw new ApiException(HttpStatus.UNAUTHORIZED, "AI_WORKER_UNAUTHORIZED",
                    "AI Worker authentication failed.");
        }
    }
}
