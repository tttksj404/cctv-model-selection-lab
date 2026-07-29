package com.ssafy.eyesonu;

import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.ssafy.eyesonu.auth.device.DeviceKeyAuthenticationFilter;
import com.ssafy.eyesonu.auth.security.AdminPrincipal;
import com.ssafy.eyesonu.mediaserver.domain.MediaServer;
import com.ssafy.eyesonu.mediaserver.mapper.MediaServerMapper;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.dao.DataAccessResourceFailureException;
import org.springframework.context.annotation.Import;
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
	void deviceKeyDoesNotAuthenticateAdminOrJetsonRoutes() throws Exception {
		mockMvc.perform(get("/api/v1/admins/me")
						.header(DeviceKeyAuthenticationFilter.HEADER_NAME, DEVICE_KEY))
				.andExpect(status().isUnauthorized())
				.andExpect(jsonPath("$.code").value("AUTHENTICATION_REQUIRED"));

		mockMvc.perform(post("/api/v1/device/candidate-events")
						.header(DeviceKeyAuthenticationFilter.HEADER_NAME, DEVICE_KEY))
				.andExpect(status().isUnauthorized())
				.andExpect(jsonPath("$.code").value("AUTHENTICATION_REQUIRED"));
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

	private void assertInvalid(String value) throws Exception {
		mockMvc.perform(get(ENDPOINT)
						.header(DeviceKeyAuthenticationFilter.HEADER_NAME, value))
				.andExpect(status().isUnauthorized())
				.andExpect(jsonPath("$.code").value("INVALID_DEVICE_KEY"));
	}

}
