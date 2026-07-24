package com.ssafy.eyesonu.auth.security;

import com.ssafy.eyesonu.common.api.ApiErrorResponse;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import org.springframework.http.MediaType;
import tools.jackson.databind.ObjectMapper;

public class SecurityErrorWriter {

	private final ObjectMapper objectMapper;

	public SecurityErrorWriter(ObjectMapper objectMapper) {
		this.objectMapper = objectMapper;
	}

	public void write(HttpServletResponse response, int status, String code, String message)
			throws IOException {
		response.setStatus(status);
		response.setCharacterEncoding("UTF-8");
		response.setContentType(MediaType.APPLICATION_JSON_VALUE);
		objectMapper.writeValue(response.getOutputStream(), ApiErrorResponse.of(status, code, message));
	}
}
