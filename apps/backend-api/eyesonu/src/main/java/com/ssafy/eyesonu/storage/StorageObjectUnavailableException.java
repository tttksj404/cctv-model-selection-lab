package com.ssafy.eyesonu.storage;

public class StorageObjectUnavailableException extends RuntimeException {

	public StorageObjectUnavailableException(Throwable cause) {
		super("Storage service is unavailable", cause);
	}
}
