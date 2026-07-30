package com.ssafy.eyesonu.missingcase.service;

import com.ssafy.eyesonu.auth.device.MediaServerPrincipal;
import com.ssafy.eyesonu.missingcase.domain.DeviceSearchTargetRow;
import com.ssafy.eyesonu.missingcase.dto.device.SearchCameraTargetResponse;
import com.ssafy.eyesonu.missingcase.dto.device.SearchConditionTargetResponse;
import com.ssafy.eyesonu.missingcase.dto.device.SearchTargetResponse;
import com.ssafy.eyesonu.missingcase.mapper.MissingCaseMapper;
import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Service;

@Service
public class DeviceSearchTargetService {

	private final MissingCaseMapper mapper;

	public DeviceSearchTargetService(MissingCaseMapper mapper) {
		this.mapper = mapper;
	}

	public List<SearchTargetResponse> findTargets(MediaServerPrincipal principal) {
		Map<Long, TargetAccumulator> grouped = new LinkedHashMap<>();
		for (DeviceSearchTargetRow row : mapper.findDeviceSearchTargets(principal.mediaServerId())) {
			TargetAccumulator target = grouped.computeIfAbsent(row.getCaseId(),
					ignored -> new TargetAccumulator(row.getCaseId(), row.getCaseNumber()));
			target.addCondition(row);
			target.addCamera(row);
			target.updateTimestamp(row.getUpdatedAt());
		}
		return grouped.values().stream().map(TargetAccumulator::toResponse).toList();
	}

	private static final class TargetAccumulator {
		private final Long caseId;
		private final String caseNumber;
		private final Map<Long, SearchConditionTargetResponse> conditions = new LinkedHashMap<>();
		private final Map<Long, SearchCameraTargetResponse> cameras = new LinkedHashMap<>();
		private Instant updatedAt;

		private TargetAccumulator(Long caseId, String caseNumber) {
			this.caseId = caseId;
			this.caseNumber = caseNumber;
		}

		private void addCondition(DeviceSearchTargetRow row) {
			conditions.putIfAbsent(row.getConditionId(), new SearchConditionTargetResponse(
					row.getConditionId(), row.getPrompt(), row.getExclusionPrompt(),
					row.getSearchStart(), row.getSearchEnd(), row.getSearchArea(),
					row.getSimilarityThreshold()));
		}

		private void addCamera(DeviceSearchTargetRow row) {
			cameras.putIfAbsent(row.getCameraId(),
					new SearchCameraTargetResponse(row.getCameraId(), row.getCameraCode()));
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
