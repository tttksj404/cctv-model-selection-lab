package com.ssafy.eyesonu.missingcase.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.ssafy.eyesonu.auth.device.MediaServerPrincipal;
import com.ssafy.eyesonu.missingcase.domain.DeviceSearchTargetRow;
import com.ssafy.eyesonu.missingcase.mapper.MissingCaseMapper;
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
		condition.setExclusionPrompt("a woman wearing a white long sleeve top and gray pants");
		when(mapper.findDeviceSearchTargetCameras(7L)).thenReturn(List.of(row(101L, 10L, 2L, updatedAt)));
		when(mapper.findDeviceSearchTargetConditions(Set.of(101L))).thenReturn(List.of(condition));
		when(promptNormalizer.normalizeOrNull(condition.getPrompt()))
				.thenReturn("a man wearing a black short sleeve top and blue pants");
		when(promptNormalizer.normalizeOrNull(condition.getExclusionPrompt()))
				.thenReturn("a woman wearing a white long sleeve top and gray pants");

		var result = new DeviceSearchTargetService(mapper, promptNormalizer)
				.findTargets(new MediaServerPrincipal(7L, "MS-001"));

		assertEquals("a man wearing a black short sleeve top and blue pants",
				result.getFirst().searchConditions().getFirst().prompt());
		assertEquals("a woman wearing a white long sleeve top and gray pants",
				result.getFirst().searchConditions().getFirst().exclusionPrompt());
		assertFalse(new ObjectMapper().findAndRegisterModules()
				.valueToTree(result.getFirst().searchConditions().getFirst())
				.has("similarityThreshold"));
		verify(promptNormalizer).normalizeOrNull(condition.getPrompt());
		verify(promptNormalizer).normalizeOrNull(condition.getExclusionPrompt());
	}

	@Test
	void normalizesOnlyTheRealtimeContract() {
		RealtimePromptNormalizer normalizer = new RealtimePromptNormalizer();

		assertEquals("a man wearing a black short sleeve top and black pants",
				normalizer.normalize("a man wearing a black short sleeve top and black jeans"));
		assertEquals("", normalizer.normalize("a person wearing a khaki windbreaker"));
		assertEquals("", normalizer.normalize("a man wearing a black short sleeve top"));
		assertEquals("a man wearing a black short sleeve top and blue pants",
				normalizer.normalize("남성, black 반팔 상의와 blue 하의"));
	}

	@Test
	void excludesConditionWhenMainPromptNormalizationFails() {
		Instant updatedAt = Instant.parse("2026-07-30T04:00:00Z");
		DeviceSearchTargetRow condition = row(101L, 10L, null, updatedAt);
		condition.setPrompt("a person wearing a khaki windbreaker");
		when(mapper.findDeviceSearchTargetCameras(7L)).thenReturn(List.of(row(101L, 10L, 2L, updatedAt)));
		when(mapper.findDeviceSearchTargetConditions(Set.of(101L))).thenReturn(List.of(condition));
		when(promptNormalizer.normalizeOrNull(condition.getPrompt())).thenReturn(null);

		var result = new DeviceSearchTargetService(mapper, promptNormalizer)
				.findTargets(new MediaServerPrincipal(7L, "MS-001"));

		assertTrue(result.isEmpty());
		verify(promptNormalizer).normalizeOrNull(condition.getPrompt());
	}

	@Test
	void excludesConditionWhenOptionalExclusionPromptNormalizationFails() {
		Instant updatedAt = Instant.parse("2026-07-30T04:00:00Z");
		DeviceSearchTargetRow condition = row(101L, 10L, null, updatedAt);
		condition.setPrompt("a man wearing a black short sleeve top and blue pants");
		condition.setExclusionPrompt("exclude a khaki windbreaker");
		when(mapper.findDeviceSearchTargetCameras(7L)).thenReturn(List.of(row(101L, 10L, 2L, updatedAt)));
		when(mapper.findDeviceSearchTargetConditions(Set.of(101L))).thenReturn(List.of(condition));
		when(promptNormalizer.normalizeOrNull(condition.getPrompt())).thenReturn(condition.getPrompt());
		when(promptNormalizer.normalizeOrNull(condition.getExclusionPrompt())).thenReturn(null);

		var result = new DeviceSearchTargetService(mapper, promptNormalizer)
				.findTargets(new MediaServerPrincipal(7L, "MS-001"));

		assertTrue(result.isEmpty());
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
		row.setCameraId(cameraId);
		if (cameraId != null) row.setCameraCode("CAM-00" + cameraId);
		row.setUpdatedAt(updatedAt);
		return row;
	}
}
