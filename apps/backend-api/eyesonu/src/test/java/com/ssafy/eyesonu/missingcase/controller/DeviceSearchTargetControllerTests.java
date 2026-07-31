package com.ssafy.eyesonu.missingcase.controller;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.ssafy.eyesonu.auth.device.MediaServerPrincipal;
import com.ssafy.eyesonu.missingcase.dto.device.SearchTargetResponse;
import com.ssafy.eyesonu.missingcase.service.DeviceSearchTargetService;
import java.time.Instant;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;

@ExtendWith(MockitoExtension.class)
class DeviceSearchTargetControllerTests {

	@Mock
	private DeviceSearchTargetService service;

	@Test
	void returnsNotModifiedWithoutLoadingFullTargetsWhenEtagMatches() {
		MediaServerPrincipal principal = new MediaServerPrincipal(7L, "MS-001");
		Instant updatedAt = Instant.parse("2026-07-30T04:00:00Z");
		when(service.findLastModified(principal)).thenReturn(updatedAt);
		when(service.findTargets(principal)).thenReturn(List.of());
		DeviceSearchTargetController controller = new DeviceSearchTargetController(service);

		ResponseEntity<?> first = controller.findTargets(principal, null);
		ResponseEntity<?> unchanged = controller.findTargets(principal, first.getHeaders().getETag());

		assertEquals(HttpStatus.OK, first.getStatusCode());
		assertNotNull(first.getHeaders().getETag());
		assertEquals(HttpStatus.NOT_MODIFIED, unchanged.getStatusCode());
		assertEquals(first.getHeaders().getETag(), unchanged.getHeaders().getETag());
		verify(service).findTargets(principal);
	}
}
