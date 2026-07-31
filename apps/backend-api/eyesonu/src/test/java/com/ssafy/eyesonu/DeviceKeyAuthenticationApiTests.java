package com.ssafy.eyesonu;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.ssafy.eyesonu.auth.device.DeviceKeyAuthenticationFilter;
import com.ssafy.eyesonu.auth.device.MediaServerPrincipal;
import com.ssafy.eyesonu.auth.security.AdminPrincipal;
import com.ssafy.eyesonu.mediaserver.domain.MediaServer;
import com.ssafy.eyesonu.mediaserver.mapper.MediaServerMapper;
import com.ssafy.eyesonu.recording.domain.Recording;
import com.ssafy.eyesonu.recording.dto.device.RecordingCreateRequest;
import com.ssafy.eyesonu.recording.service.RecordingCommandService;
import com.ssafy.eyesonu.recording.service.RecordingCreateResult;
import java.time.Instant;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.context.annotation.Import;
import org.springframework.dao.DataAccessResourceFailureException;
import org.springframework.http.MediaType;
import org.springframework.mock.web.MockHttpSession;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContext;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.context.HttpSessionSecurityContextRepository;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

@ActiveProfiles("test")
@SpringBootTest(useMainMethod = SpringBootTest.UseMainMethod.ALWAYS)
@Import(TestDatabaseConfiguration.class)
@AutoConfigureMockMvc
class DeviceKeyAuthenticationApiTests {

	private static final String KEY_ID = "0123456789abcdef";
	private static final String SECRET =
			"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";
	private static final String DEVICE_KEY = "msk_" + KEY_ID + "." + SECRET;
	private static final String ENDPOINT = "/api/v1/device/media-server/ping";

	@Autowired
	private MockMvc mockMvc;

	@Autowired
	private PasswordEncoder passwordEncoder;

	@MockitoBean
	private MediaServerMapper mediaServerMapper;

	@MockitoBean
	private RecordingCommandService recordingCommandService;

	private MediaServer activeServer;

	@BeforeEach
	void setUp() {
		activeServer = new MediaServer(
				7L,
				"rpi5-media-01",
				"Raspberry Pi 5 Media Server",
				KEY_ID,
				passwordEncoder.encode(SECRET),
				"ACTIVE");
		when(mediaServerMapper.findByDeviceKeyId(KEY_ID)).thenReturn(Optional.of(activeServer));
	}

	@Test
	void missingDeviceKeyReturnsAuthenticationRequired() throws Exception {
		mockMvc.perform(get(ENDPOINT))
				.andExpect(status().isUnauthorized())
				.andExpect(jsonPath("$.code").value("AUTHENTICATION_REQUIRED"));
	}

	@Test
	void administratorSessionDoesNotAuthenticateDeviceRoute() throws Exception {
		AdminPrincipal admin = new AdminPrincipal(1L, "admin");
		SecurityContext context = SecurityContextHolder.createEmptyContext();
		context.setAuthentication(new UsernamePasswordAuthenticationToken(
				admin, null, admin.getAuthorities()));
		MockHttpSession session = new MockHttpSession();
		session.setAttribute(
				HttpSessionSecurityContextRepository.SPRING_SECURITY_CONTEXT_KEY, context);

		mockMvc.perform(get(ENDPOINT).session(session))
				.andExpect(status().isUnauthorized())
				.andExpect(jsonPath("$.code").value("AUTHENTICATION_REQUIRED"));
	}

	@Test
	void malformedUnknownWrongAndDisabledKeysReturnInvalidDeviceKey() throws Exception {
		assertInvalid("invalid");

		String unknown = "msk_fedcba9876543210." + SECRET;
		when(mediaServerMapper.findByDeviceKeyId("fedcba9876543210")).thenReturn(Optional.empty());
		assertInvalid(unknown);

		String wrongSecret = "f" + SECRET.substring(1);
		assertInvalid("msk_" + KEY_ID + "." + wrongSecret);

		when(mediaServerMapper.findByDeviceKeyId(KEY_ID)).thenReturn(Optional.of(
				new MediaServer(
						activeServer.id(),
						activeServer.serverCode(),
						activeServer.name(),
						activeServer.deviceKeyId(),
						activeServer.deviceKeyHash(),
						"DISABLED")));
		assertInvalid(DEVICE_KEY);
	}

	@Test
	void validKeyCreatesPrincipalWithoutSessionOrCsrf() throws Exception {
		MvcResult result = mockMvc.perform(get(ENDPOINT)
						.header(DeviceKeyAuthenticationFilter.HEADER_NAME, DEVICE_KEY))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.authenticated").value(true))
				.andExpect(jsonPath("$.data.mediaServerId").value(7))
				.andExpect(jsonPath("$.data.serverCode").value("rpi5-media-01"))
				.andReturn();

		org.junit.jupiter.api.Assertions.assertNull(result.getRequest().getSession(false));
		org.junit.jupiter.api.Assertions.assertNull(result.getResponse().getCookie("EYESONU_SESSION"));
	}

	@Test
	void deviceKeyDoesNotAuthenticateAdminButAuthenticatesEveryDeviceRoute() throws Exception {
		mockMvc.perform(get("/api/v1/admins/me")
						.header(DeviceKeyAuthenticationFilter.HEADER_NAME, DEVICE_KEY))
				.andExpect(status().isUnauthorized())
				.andExpect(jsonPath("$.code").value("AUTHENTICATION_REQUIRED"));

		mockMvc.perform(post("/api/v1/device/__security-probe-for-not-found__")
						.header(DeviceKeyAuthenticationFilter.HEADER_NAME, DEVICE_KEY))
				.andExpect(status().isNotFound());
	}

	@Test
	void authenticationDatabaseFailureReturnsServiceUnavailable() throws Exception {
		when(mediaServerMapper.findByDeviceKeyId(KEY_ID))
				.thenThrow(new DataAccessResourceFailureException("database unavailable"));

		mockMvc.perform(get(ENDPOINT)
						.header(DeviceKeyAuthenticationFilter.HEADER_NAME, DEVICE_KEY))
				.andExpect(status().isServiceUnavailable())
				.andExpect(jsonPath("$.code").value("AUTHENTICATION_UNAVAILABLE"));
	}

	@Test
	void recordingPostPassesAuthenticatedPrincipalAndReturnsCreatedOrReplayStatus() throws Exception {
		String path = "/api/v1/device/cameras/CAM-001/recordings";
		String idempotencyKey = "550e8400-e29b-41d4-a716-446655440000";
		Recording recording = new Recording(
				99L,
				11L,
				Instant.parse("2026-07-20T01:00:00Z"),
				Instant.parse("2026-07-20T01:01:00Z"),
				"recordings/CAM-001/video.mp4",
				80L,
				Instant.parse("2026-07-20T01:01:01Z"));
		when(recordingCommandService.create(
				any(MediaServerPrincipal.class),
				eq("CAM-001"),
				eq(idempotencyKey),
				any(RecordingCreateRequest.class)))
				.thenReturn(new RecordingCreateResult(recording, false))
				.thenReturn(new RecordingCreateResult(recording, true));

		mockMvc.perform(post(path)
					.header(DeviceKeyAuthenticationFilter.HEADER_NAME, DEVICE_KEY)
					.header("Idempotency-Key", idempotencyKey)
					.contentType(MediaType.APPLICATION_JSON)
					.content(validRecordingJson()))
				.andExpect(status().isCreated())
				.andExpect(jsonPath("$.data.id").value(99))
				.andExpect(jsonPath("$.data.fileSize").value(80))
				.andExpect(jsonPath("$.data.duplicate").value(false))
				.andExpect(jsonPath("$.data.startTime").value("2026-07-20T01:00:00Z"))
				.andExpect(jsonPath("$.data.createdAt").value("2026-07-20T01:01:01Z"));

		mockMvc.perform(post(path)
					.header(DeviceKeyAuthenticationFilter.HEADER_NAME, DEVICE_KEY)
					.header("Idempotency-Key", idempotencyKey)
					.contentType(MediaType.APPLICATION_JSON)
					.content(validRecordingJson()))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.duplicate").value(true));

		var principalCaptor = org.mockito.ArgumentCaptor.forClass(MediaServerPrincipal.class);
		verify(recordingCommandService, org.mockito.Mockito.times(2)).create(
				principalCaptor.capture(), eq("CAM-001"), eq(idempotencyKey), any());
		org.junit.jupiter.api.Assertions.assertTrue(principalCaptor.getAllValues().stream()
				.allMatch(principal -> principal.mediaServerId().equals(7L)
						&& principal.serverCode().equals("rpi5-media-01")));
	}

	@Test
	void recordingPostReturnsStructuredErrorsForHeaderMediaTypeAndTimeSyntax() throws Exception {
		String path = "/api/v1/device/cameras/CAM-001/recordings";
		String idempotencyKey = "550e8400-e29b-41d4-a716-446655440000";

		mockMvc.perform(post(path)
					.header(DeviceKeyAuthenticationFilter.HEADER_NAME, DEVICE_KEY)
					.contentType(MediaType.APPLICATION_JSON)
					.content(validRecordingJson()))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("VALIDATION_ERROR"));

		mockMvc.perform(post(path)
					.header(DeviceKeyAuthenticationFilter.HEADER_NAME, DEVICE_KEY)
					.header("Idempotency-Key", idempotencyKey)
					.contentType(MediaType.TEXT_PLAIN)
					.content(validRecordingJson()))
				.andExpect(status().isUnsupportedMediaType())
				.andExpect(jsonPath("$.code").value("UNSUPPORTED_MEDIA_TYPE"));

		mockMvc.perform(post(path)
					.header(DeviceKeyAuthenticationFilter.HEADER_NAME, DEVICE_KEY)
					.header("Idempotency-Key", idempotencyKey)
					.contentType(MediaType.APPLICATION_JSON)
					.content(validRecordingJson().replace("01:00:00Z", "01:00:00")))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("VALIDATION_ERROR"));

		mockMvc.perform(post(path)
					.header(DeviceKeyAuthenticationFilter.HEADER_NAME, DEVICE_KEY)
					.header("Idempotency-Key", idempotencyKey)
					.contentType(MediaType.APPLICATION_JSON)
					.content(validRecordingJson().replace("01:00:00Z", "01:00:00.1234567Z")))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("VALIDATION_ERROR"));

		verify(recordingCommandService, never()).create(any(), any(), any(), any());
	}

	private void assertInvalid(String value) throws Exception {
		mockMvc.perform(get(ENDPOINT)
						.header(DeviceKeyAuthenticationFilter.HEADER_NAME, value))
				.andExpect(status().isUnauthorized())
				.andExpect(jsonPath("$.code").value("INVALID_DEVICE_KEY"));
	}

	private String validRecordingJson() {
		return """
				{
				  "startTime": "2026-07-20T01:00:00Z",
				  "endTime": "2026-07-20T01:01:00Z",
				  "objectKey": "recordings/CAM-001/video.mp4"
				}
				""";
	}

}
