package com.ssafy.eyesonu.missingcase.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.when;

import com.ssafy.eyesonu.common.config.properties.S3Properties;
import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.missingcase.dto.device.CandidateEventCreateRequest;
import com.ssafy.eyesonu.storage.StorageObject;
import com.ssafy.eyesonu.storage.StorageObjectNotFoundException;
import com.ssafy.eyesonu.storage.StorageObjectVerifier;
import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class CandidateEventStorageValidatorTests {

    @Mock private StorageObjectVerifier storageObjectVerifier;

    private CandidateEventStorageValidator validator;

    @BeforeEach
    void setUp() {
        S3Properties properties = new S3Properties();
        properties.setCandidateImageMaxFileSizeBytes(10 * 1024 * 1024);
        validator = new CandidateEventStorageValidator(storageObjectVerifier, properties);
    }

    @Test
    void acceptsObjectsWhenExtensionAndContentTypeMatch() {
        when(storageObjectVerifier.stat("frames/frame.jpg"))
                .thenReturn(new StorageObject(100L, "image/jpeg"));
        when(storageObjectVerifier.stat("crops/crop.png"))
                .thenReturn(new StorageObject(50L, "image/png"));

        validator.verify(request("frames/frame.jpg", "crops/crop.png"));
    }

    @Test
    void rejectsJpegKeyContainingPngObject() {
        when(storageObjectVerifier.stat("frames/frame.jpg"))
                .thenReturn(new StorageObject(100L, "image/png"));

        ApiException exception = assertThrows(ApiException.class, () ->
                validator.verify(request("frames/frame.jpg", "crops/crop.png")));

        assertEquals("STORAGE_OBJECT_TYPE_MISMATCH", exception.getCode());
    }

    @Test
    void rejectsUnsupportedFileExtension() {
        when(storageObjectVerifier.stat("frames/frame.gif"))
                .thenReturn(new StorageObject(100L, "image/gif"));

        ApiException exception = assertThrows(ApiException.class, () ->
                validator.verify(request("frames/frame.gif", "crops/crop.png")));

        assertEquals("STORAGE_OBJECT_TYPE_INVALID", exception.getCode());
    }

    @Test
    void rejectsCandidateImageLargerThanConfiguredLimit() {
        when(storageObjectVerifier.stat("frames/frame.jpg"))
                .thenReturn(new StorageObject(10 * 1024 * 1024 + 1L, "image/jpeg"));

        ApiException exception = assertThrows(ApiException.class, () ->
                validator.verify(request("frames/frame.jpg", "crops/crop.png")));

        assertEquals("STORAGE_OBJECT_TOO_LARGE", exception.getCode());
    }

    @Test
    void mapsMissingStorageObjectToApiError() {
        when(storageObjectVerifier.stat("frames/frame.jpg"))
                .thenThrow(new StorageObjectNotFoundException(new IllegalStateException("missing")));

        ApiException exception = assertThrows(ApiException.class, () ->
                validator.verify(request("frames/frame.jpg", "crops/crop.png")));

        assertEquals("STORAGE_OBJECT_NOT_FOUND", exception.getCode());
    }

    private CandidateEventCreateRequest request(String frameKey, String cropKey) {
        return new CandidateEventCreateRequest(
                101L, "CAM-001", "event-1", OffsetDateTime.parse("2026-08-02T10:00:00Z"),
                frameKey, List.of(new CandidateEventCreateRequest.Detection(
                        "track-1", new BigDecimal("0.91"), cropKey,
                        new CandidateEventCreateRequest.BoundingBox(1, 2, 30, 40))));
    }
}
