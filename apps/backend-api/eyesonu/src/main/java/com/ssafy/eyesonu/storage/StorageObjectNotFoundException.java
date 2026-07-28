package com.ssafy.eyesonu.storage;

public class StorageObjectNotFoundException extends RuntimeException {

    public StorageObjectNotFoundException(String objectKey, Throwable cause) {
        super("Storage object was not found: " + objectKey, cause);
    }
}
