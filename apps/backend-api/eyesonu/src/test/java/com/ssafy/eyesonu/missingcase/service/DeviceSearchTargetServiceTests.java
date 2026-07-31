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
import java.util.Set;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class DeviceSearchTargetServiceTests {

	@Mock
	private MissingCaseMapper mapper;

	@Mock
	private RealtimePromptNormalizer promptNormalizer;

	@Test
	void appliesRealtimeNormalizerWhenBuildingDeviceResponse() {
		Instant updatedAt = Instant.parse("2026-07-30T04:00:00Z");
		DeviceSearchTargetRow condition = row(101L, 10L, null, updatedAt);
		condition.setPrompt("남성, 검은색 반팔 상의와 파란색 하의");
		condition.setExclusionPrompt("제외 조건");
		when(mapper.findDeviceSearchTargetCameras(7L)).thenReturn(List.of(row(101L, 10L, 2L, updatedAt)));
		when(mapper.findDeviceSearchTargetConditions(Set.of(101L))).thenReturn(List.of(condition));
		when(promptNormalizer.normalize(condition.getPrompt()))
				.thenReturn("a man wearing a black short sleeve top and blue pants");
		when(promptNormalizer.normalize(condition.getExclusionPrompt())).thenReturn("");

		var result = new DeviceSearchTargetService(mapper, promptNormalizer)
				.findTargets(new MediaServerPrincipal(7L, "MS-001"));

		assertEquals("a man wearing a black short sleeve top and blue pants",
				result.getFirst().searchConditions().getFirst().prompt());
		assertEquals("", result.getFirst().searchConditions().getFirst().exclusionPrompt());
		verify(promptNormalizer).normalize(condition.getPrompt());
		verify(promptNormalizer).normalize(condition.getExclusionPrompt());
	}

	@Test
	void normalizesOnlyTheRealtimeContract() {
		RealtimePromptNormalizer normalizer = new RealtimePromptNormalizer();

		assertEquals("a man wearing a black short sleeve top and black pants",
				normalizer.normalize("a man wearing a black short sleeve top and black jeans"));
		assertEquals("", normalizer.normalize("a person wearing a khaki windbreaker"));
	}

	@Test
	void readsLastModifiedForTheAuthenticatedMediaServer() {
		Instant updatedAt = Instant.parse("2026-07-30T04:00:00Z");
		when(mapper.findDeviceSearchTargetLastModified(7L)).thenReturn(updatedAt);

		var result = new DeviceSearchTargetService(mapper, promptNormalizer)
				.findLastModified(new MediaServerPrincipal(7L, "MS-001"));

		assertEquals(updatedAt, result);
		verify(mapper).findDeviceSearchTargetLastModified(7L);
	}

	private DeviceSearchTargetRow row(Long caseId, Long conditionId, Long cameraId, Instant updatedAt) {
		DeviceSearchTargetRow row = new DeviceSearchTargetRow();
		row.setCaseId(caseId);
		row.setCaseNumber("EFU-CASE-101");
		row.setConditionId(conditionId);
		row.setPrompt("black shirt");
		row.setSimilarityThreshold(new BigDecimal("0.72"));
		row.setCameraId(cameraId);
		if (cameraId != null) row.setCameraCode("CAM-00" + cameraId);
		row.setUpdatedAt(updatedAt);
		return row;
	}
}
