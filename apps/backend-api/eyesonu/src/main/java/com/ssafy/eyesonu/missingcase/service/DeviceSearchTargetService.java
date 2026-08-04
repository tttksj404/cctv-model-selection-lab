package com.ssafy.eyesonu.missingcase.service;

import com.ssafy.eyesonu.auth.device.MediaServerPrincipal;
import com.ssafy.eyesonu.missingcase.domain.DeviceSearchTargetRow;
import com.ssafy.eyesonu.missingcase.dto.device.SearchCameraTargetResponse;
import com.ssafy.eyesonu.missingcase.dto.device.SearchConditionTargetResponse;
import com.ssafy.eyesonu.missingcase.dto.device.SearchTargetResponse;
import com.ssafy.eyesonu.missingcase.mapper.MissingCaseMapper;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Collection;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Service;

@Service
public class DeviceSearchTargetService {

	private final MissingCaseMapper mapper;
	private final RealtimePromptNormalizer promptNormalizer;

	public DeviceSearchTargetService(MissingCaseMapper mapper, RealtimePromptNormalizer promptNormalizer) {
		this.mapper = mapper;
		this.promptNormalizer = promptNormalizer;
	}

	public List<SearchTargetResponse> findTargets(MediaServerPrincipal principal) {
		Map<Long, TargetAccumulator> grouped = new LinkedHashMap<>();
		for (DeviceSearchTargetRow row : mapper.findDeviceSearchTargetCameras(principal.mediaServerId())) {
			TargetAccumulator target = grouped.computeIfAbsent(row.getCaseId(),
					ignored -> new TargetAccumulator(row.getCaseId(), row.getCaseNumber(), promptNormalizer));
			target.addCamera(row);
			target.updateTimestamp(row.getUpdatedAt());
		}
		if (grouped.isEmpty()) return List.of();

		Collection<Long> caseIds = grouped.keySet();
		for (DeviceSearchTargetRow row : mapper.findDeviceSearchTargetConditions(caseIds)) {
			TargetAccumulator target = grouped.get(row.getCaseId());
			if (target == null) continue;
			target.addCondition(row);
			target.updateTimestamp(row.getUpdatedAt());
		}
		return grouped.values().stream()
				.filter(TargetAccumulator::hasConditions)
				.map(TargetAccumulator::toResponse)
				.toList();
	}

	public Instant findLastModified(MediaServerPrincipal principal) {
		return mapper.findDeviceSearchTargetLastModified(principal.mediaServerId());
	}

	private static final class TargetAccumulator {
		private final Long caseId;
		private final String caseNumber;
		private final RealtimePromptNormalizer promptNormalizer;
		private final Map<Long, SearchConditionTargetResponse> conditions = new LinkedHashMap<>();
		private final Map<Long, SearchCameraTargetResponse> cameras = new LinkedHashMap<>();
		private Instant updatedAt;

		private TargetAccumulator(Long caseId, String caseNumber, RealtimePromptNormalizer promptNormalizer) {
			this.caseId = caseId;
			this.caseNumber = caseNumber;
			this.promptNormalizer = promptNormalizer;
		}

		private void addCondition(DeviceSearchTargetRow row) {
			String prompt = promptNormalizer.normalizeOrNull(row.getPrompt());
			if (prompt == null) return;
			String exclusionPrompt = null;
			if (row.getExclusionPrompt() != null && !row.getExclusionPrompt().isBlank()) {
				exclusionPrompt = promptNormalizer.normalizeOrNull(row.getExclusionPrompt());
				if (exclusionPrompt == null) return;
			}
			conditions.putIfAbsent(row.getConditionId(), new SearchConditionTargetResponse(
					row.getConditionId(),
					prompt,
					exclusionPrompt,
					row.getSearchStart(), row.getSearchEnd(), row.getSearchArea()));
		}

		private void addCamera(DeviceSearchTargetRow row) {
			cameras.putIfAbsent(row.getCameraId(),
					new SearchCameraTargetResponse(row.getCameraId(), row.getCameraCode()));
		}

		private boolean hasConditions() {
			return !conditions.isEmpty();
		}

		private void updateTimestamp(Instant candidate) {
			if (candidate != null && (updatedAt == null || candidate.isAfter(updatedAt))) {
				updatedAt = candidate;
			}
		}

		private SearchTargetResponse toResponse() {
			return new SearchTargetResponse(caseId, caseNumber,
					new ArrayList<>(conditions.values()), new ArrayList<>(cameras.values()), updatedAt);
		}
	}
}
