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
	private EmbeddedPromptTranslator promptTranslator;

	@Test
	void keepsLatestSettingChangeWhenActiveConditionIsOlder() {
		Instant updatedAt = Instant.parse("2026-07-30T04:00:00Z");
		when(mapper.findDeviceSearchTargetCameras(7L)).thenReturn(List.of(
				row(101L, 10L, 2L, updatedAt),
				row(101L, 10L, 3L, updatedAt.plusSeconds(7200))));
		when(mapper.findDeviceSearchTargetConditions(Set.of(101L))).thenReturn(List.of(
				row(101L, 10L, null, updatedAt)));
		when(promptTranslator.translate("black shirt")).thenReturn("a person wearing a black top");

		var result = new DeviceSearchTargetService(mapper, promptTranslator)
				.findTargets(new MediaServerPrincipal(7L, "MS-001"));

		assertEquals(1, result.size());
		assertEquals(1, result.getFirst().searchConditions().size());
		assertEquals("a person wearing a black top", result.getFirst().searchConditions().getFirst().prompt());
		assertEquals(2, result.getFirst().cameras().size());
		assertEquals(updatedAt.plusSeconds(7200), result.getFirst().updatedAt());
		verify(mapper).findDeviceSearchTargetCameras(7L);
		verify(mapper).findDeviceSearchTargetConditions(Set.of(101L));
	}

	@Test
	void translatesKoreanPromptAndDropsUnsupportedInformationForEmbedded() {
		Instant updatedAt = Instant.parse("2026-07-30T04:00:00Z");
		DeviceSearchTargetRow condition = row(101L, 10L, null, updatedAt);
		condition.setPrompt("70대 여성, 검은색 상의와 파란색 하의, 긴팔 긴바지");
		condition.setExclusionPrompt("모자 착용");
		when(mapper.findDeviceSearchTargetCameras(7L)).thenReturn(List.of(row(101L, 10L, 2L, updatedAt)));
		when(mapper.findDeviceSearchTargetConditions(Set.of(101L))).thenReturn(List.of(condition));
		when(promptTranslator.translate(condition.getPrompt())).thenReturn("a woman wearing a black long sleeve top and blue long pants");
		when(promptTranslator.translate(condition.getExclusionPrompt())).thenReturn("");

		var result = new DeviceSearchTargetService(mapper, promptTranslator)
				.findTargets(new MediaServerPrincipal(7L, "MS-001"));

		assertEquals("a woman wearing a black long sleeve top and blue long pants",
				result.getFirst().searchConditions().getFirst().prompt());
		assertEquals("", result.getFirst().searchConditions().getFirst().exclusionPrompt());
	}

	@Test
	void keepsTheRequestedEnglishPromptShape() {
		assertEquals("a man wearing a black short sleeve top and black jeans",
				new EmbeddedPromptTranslator().translate("a man wearing a black short sleeve top and black jeans"));
	}

	@Test
	void readsLastModifiedForTheAuthenticatedMediaServer() {
		Instant updatedAt = Instant.parse("2026-07-30T04:00:00Z");
		when(mapper.findDeviceSearchTargetLastModified(7L)).thenReturn(updatedAt);

		var result = new DeviceSearchTargetService(mapper, promptTranslator)
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
