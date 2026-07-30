package com.ssafy.eyesonu.missingcase.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.ssafy.eyesonu.auth.device.MediaServerPrincipal;
import com.ssafy.eyesonu.missingcase.domain.DeviceSearchTargetRow;
import com.ssafy.eyesonu.missingcase.mapper.MissingCaseMapper;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class DeviceSearchTargetServiceTests {

	@Mock
	private MissingCaseMapper mapper;

	@Test
	void groupsRepeatedJoinRowsByCaseAndDeduplicatesConditionsAndCameras() {
		Instant updatedAt = Instant.parse("2026-07-30T04:00:00Z");
		when(mapper.findDeviceSearchTargets(7L)).thenReturn(List.of(
				row(101L, 10L, 2L, updatedAt),
				row(101L, 10L, 3L, updatedAt.plusSeconds(1))));

		var result = new DeviceSearchTargetService(mapper)
				.findTargets(new MediaServerPrincipal(7L, "MS-001"));

		assertEquals(1, result.size());
		assertEquals(1, result.getFirst().searchConditions().size());
		assertEquals(2, result.getFirst().cameras().size());
		assertEquals(updatedAt.plusSeconds(1), result.getFirst().updatedAt());
		verify(mapper).findDeviceSearchTargets(7L);
	}

	private DeviceSearchTargetRow row(Long caseId, Long conditionId, Long cameraId, Instant updatedAt) {
		DeviceSearchTargetRow row = new DeviceSearchTargetRow();
		row.setCaseId(caseId);
		row.setCaseNumber("EFU-CASE-101");
		row.setConditionId(conditionId);
		row.setPrompt("black shirt");
		row.setSimilarityThreshold(new BigDecimal("0.72"));
		row.setCameraId(cameraId);
		row.setCameraCode("CAM-00" + cameraId);
		row.setUpdatedAt(updatedAt);
		return row;
	}
}
