package com.ssafy.eyesonu.storage;

public interface StorageObjectUrlSigner {

	String createGetUrl(String objectKey);

	String createPutUrl(String objectKey);
}
