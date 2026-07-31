package com.ssafy.eyesonu.missingcase.domain;

import java.math.BigDecimal;
import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
public class CandidateEventDetection {
    private Long id;
    private Long candidateEventId;
    private Long candidateId;
    private Integer detectionIndex;
    private String trackId;
    private String cropObjectKey;
    private BigDecimal similarity;
    private String boundingBox;
}
