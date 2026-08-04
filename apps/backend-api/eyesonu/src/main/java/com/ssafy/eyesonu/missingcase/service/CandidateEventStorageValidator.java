package com.ssafy.eyesonu.missingcase.service;

import com.ssafy.eyesonu.common.config.properties.MinioProperties;
import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.missingcase.dto.device.CandidateEventCreateRequest;
import com.ssafy.eyesonu.storage.StorageObject;
import com.ssafy.eyesonu.storage.StorageObjectNotFoundException;
import com.ssafy.eyesonu.storage.StorageObjectUnavailableException;
import com.ssafy.eyesonu.storage.StorageObjectVerifier;
import java.util.Locale;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;

@Service
public class CandidateEventStorageValidator {

    private static final int IMAGE_SIGNATURE_LENGTH = 8;
    private static final byte[] PNG_SIGNATURE = {
            (byte) 0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a
    };

    private final StorageObjectVerifier storageObjectVerifier;
    private final MinioProperties minioProperties;

    public CandidateEventStorageValidator(
            StorageObjectVerifier storageObjectVerifier,
            MinioProperties minioProperties) {
        this.storageObjectVerifier = storageObjectVerifier;
        this.minioProperties = minioProperties;
    }

    public void verify(CandidateEventCreateRequest request) {
        verifyObject(request.frameObjectKey());
        request.detections().forEach(detection -> verifyObject(detection.cropObjectKey()));
    }

    private void verifyObject(String key) {
        try {
            StorageObject object = storageObjectVerifier.stat(key);
            if (object.size() <= 0) {
                throw new ApiException(HttpStatus.UNPROCESSABLE_CONTENT,
                        "STORAGE_OBJECT_INVALID", "Storage object is empty");
            }
            if (object.size() > minioProperties.getCandidateImageMaxFileSizeBytes()) {
                throw new ApiException(HttpStatus.UNPROCESSABLE_CONTENT,
                        "STORAGE_OBJECT_TOO_LARGE", "Storage object is too large");
            }
            String expectedContentType = expectedContentType(key);
            String actualContentType = normalizeContentType(object.contentType());
            if (!expectedContentType.equals(actualContentType)) {
                throw new ApiException(HttpStatus.UNPROCESSABLE_CONTENT,
                        "STORAGE_OBJECT_TYPE_MISMATCH",
                        "Storage object content type does not match its file extension");
            }
            byte[] prefix = storageObjectVerifier.readPrefix(key, IMAGE_SIGNATURE_LENGTH);
            if (!matchesImageSignature(expectedContentType, prefix)) {
                throw new ApiException(HttpStatus.UNPROCESSABLE_CONTENT,
                        "STORAGE_OBJECT_CONTENT_INVALID",
                        "Storage object bytes do not match the declared image type");
            }
        } catch (StorageObjectNotFoundException exception) {
            throw new ApiException(HttpStatus.UNPROCESSABLE_CONTENT,
                    "STORAGE_OBJECT_NOT_FOUND", "Storage object was not found");
        } catch (StorageObjectUnavailableException exception) {
            throw new ApiException(HttpStatus.SERVICE_UNAVAILABLE,
                    "STORAGE_UNAVAILABLE", "Storage object could not be verified");
        }
    }

    private String expectedContentType(String key) {
        String normalized = key.toLowerCase(Locale.ROOT);
        if (normalized.endsWith(".jpg") || normalized.endsWith(".jpeg")) {
            return "image/jpeg";
        }
        if (normalized.endsWith(".png")) {
            return "image/png";
        }
        throw new ApiException(HttpStatus.UNPROCESSABLE_CONTENT,
                "STORAGE_OBJECT_TYPE_INVALID", "Storage object must use a JPEG or PNG extension");
    }

    private String normalizeContentType(String contentType) {
        if (contentType == null) {
            return "";
        }
        return contentType.split(";", 2)[0].trim().toLowerCase(Locale.ROOT);
    }

    private boolean matchesImageSignature(String contentType, byte[] prefix) {
        if (prefix == null) {
            return false;
        }
        if ("image/jpeg".equals(contentType)) {
            return prefix.length >= 3
                    && prefix[0] == (byte) 0xff
                    && prefix[1] == (byte) 0xd8
                    && prefix[2] == (byte) 0xff;
        }
        if (prefix.length < PNG_SIGNATURE.length) {
            return false;
        }
        for (int index = 0; index < PNG_SIGNATURE.length; index++) {
            if (prefix[index] != PNG_SIGNATURE[index]) {
                return false;
            }
        }
        return true;
    }
}
