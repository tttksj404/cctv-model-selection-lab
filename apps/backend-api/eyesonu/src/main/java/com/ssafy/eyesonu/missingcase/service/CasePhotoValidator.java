package com.ssafy.eyesonu.missingcase.service;

import com.ssafy.eyesonu.common.config.properties.MinioProperties;
import com.ssafy.eyesonu.common.exception.ApiException;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.Locale;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.multipart.MultipartFile;

@Component
public class CasePhotoValidator {

	private static final byte[] PNG = new byte[] {
			(byte) 0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a
	};

	private final MinioProperties properties;

	public CasePhotoValidator(MinioProperties properties) {
		this.properties = properties;
	}

	public ValidatedPhoto validate(MultipartFile file) {
		if (file == null || file.isEmpty()) {
			throw validation("사진 파일이 필요합니다.");
		}
		if (file.getSize() > properties.getCasePhotoMaxFileSizeBytes()) {
			throw new ApiException(HttpStatus.PAYLOAD_TOO_LARGE, "FILE_TOO_LARGE", "사진은 10MB 이하여야 합니다.");
		}
		byte[] bytes;
		try {
			bytes = file.getBytes();
		}
		catch (IOException exception) {
			throw new ApiException(HttpStatus.BAD_REQUEST, "INVALID_FILE", "사진 파일을 읽을 수 없습니다.");
		}
		DetectedImage detected = detect(bytes);
		String declared = file.getContentType() == null
				? "" : file.getContentType().toLowerCase(Locale.ROOT);
		if (declared.equals("image/jpg")) declared = "image/jpeg";
		if (!declared.equals(detected.contentType())) {
			throw unsupported();
		}
		return new ValidatedPhoto(bytes, detected.contentType(), detected.extension());
	}

	private DetectedImage detect(byte[] bytes) {
		if (bytes.length >= 3
				&& (bytes[0] & 0xff) == 0xff
				&& (bytes[1] & 0xff) == 0xd8
				&& (bytes[2] & 0xff) == 0xff) {
			return new DetectedImage("image/jpeg", "jpg");
		}
		if (bytes.length >= PNG.length
				&& Arrays.equals(Arrays.copyOf(bytes, PNG.length), PNG)) {
			return new DetectedImage("image/png", "png");
		}
		if (bytes.length >= 12
				&& ascii(bytes, 0, 4).equals("RIFF")
				&& ascii(bytes, 8, 12).equals("WEBP")) {
			return new DetectedImage("image/webp", "webp");
		}
		throw unsupported();
	}

	private String ascii(byte[] bytes, int from, int to) {
		return new String(bytes, from, to - from, StandardCharsets.US_ASCII);
	}

	private ApiException unsupported() {
		return new ApiException(
				HttpStatus.UNSUPPORTED_MEDIA_TYPE,
				"UNSUPPORTED_MEDIA_TYPE",
				"JPEG, PNG, WebP 이미지만 업로드할 수 있습니다.");
	}

	private ApiException validation(String message) {
		return new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_ERROR", message);
	}

	public record ValidatedPhoto(byte[] bytes, String contentType, String extension) {
	}

	private record DetectedImage(String contentType, String extension) {
	}
}
