package com.ssafy.eyesonu.storage;

public class StorageObjectUnavailableException extends RuntimeException {

    public StorageObjectUnavailableException(String objectKey, Throwable cause) {
        super("Storage object could not be verified: " + objectKey, cause);
    }
}
