package com.ssafy.eyesonu.storage;

public interface StorageObjectVerifier {

    StorageObject stat(String objectKey);

    byte[] readPrefix(String objectKey, int length);
}
