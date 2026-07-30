package com.ssafy.eyesonu.missingcase.domain;

import java.math.BigDecimal;
import java.time.Instant;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@NoArgsConstructor
public class SearchConditionRow {

	private Long id;
	private Long caseId;
	private String prompt;
	private String exclusionPrompt;
	private Instant searchStart;
	private Instant searchEnd;
	private String searchArea;
	private BigDecimal similarityThreshold;
	private Instant createdAt;
	private Instant updatedAt;
}
