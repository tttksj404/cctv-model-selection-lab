package com.ssafy.eyesonu.storage;

public class StorageObjectNotFoundException extends RuntimeException {

	public StorageObjectNotFoundException(Throwable cause) {
		super("Storage object was not found", cause);
	}
}
