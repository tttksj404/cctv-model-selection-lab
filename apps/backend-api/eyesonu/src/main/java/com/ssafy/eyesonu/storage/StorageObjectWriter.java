package com.ssafy.eyesonu.storage;

public interface StorageObjectWriter {

	void put(String objectKey, byte[] content, String contentType);

	void delete(String objectKey);
}
