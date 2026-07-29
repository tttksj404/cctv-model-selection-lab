package com.ssafy.eyesonu.missingcase.domain;

import java.math.BigDecimal;
import java.time.Instant;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
public class MissingCaseRow {

	private Long id;
	private Long reporterId;
	private String reporterName;
	private String reporterPhone;
	private String reporterEmail;
	private String reporterRelation;
	private String caseNumber;
	private CaseStatus status;
	private String reportContent;
	private String missingName;
	private Gender gender;
	private Integer birthYear;
	private String hair;
	private String face;
	private String upperClothing;
	private String lowerClothing;
	private String shoes;
	private String belongings;
	private String bodyType;
	private String distinctiveFeatures;
	private String photoS3Key;
	private Instant lastSeenTime;
	private BigDecimal lastSeenLat;
	private BigDecimal lastSeenLng;
	private String lastSeenAddress;
	private Instant reportedAt;
	private Instant closedAt;
	private Instant createdAt;
	private Instant updatedAt;
}
