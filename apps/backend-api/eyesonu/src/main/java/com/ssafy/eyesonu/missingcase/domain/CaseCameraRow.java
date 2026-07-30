package com.ssafy.eyesonu.missingcase.domain;

import java.time.Instant;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@NoArgsConstructor
public class CaseCameraRow {

	private Long id;
	private Long caseId;
	private Long cameraId;
	private String cameraCode;
	private String cameraName;
	private boolean searchEnabled;
	private Instant selectedAt;
	private Instant removedAt;
}
