package com.ssafy.eyesonu.missingcase.mapper;

import com.ssafy.eyesonu.missingcase.domain.CandidateAggregate;
import com.ssafy.eyesonu.missingcase.domain.CandidateEvent;
import com.ssafy.eyesonu.missingcase.domain.CandidateEventDetection;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

@Mapper
public interface CandidateEventMapper {
    CandidateEvent findEventByEventId(@Param("eventId") String eventId);
    List<CandidateEventDetection> findDetectionsByEventId(@Param("eventId") String eventId);
    boolean existsActiveCaseCamera(@Param("caseId") Long caseId, @Param("cameraId") Long cameraId);
    void insertEvent(@Param("event") CandidateEvent event);
    CandidateAggregate findCandidateForUpdate(@Param("caseId") Long caseId,
                                               @Param("cameraId") Long cameraId,
                                               @Param("trackId") String trackId);
    void insertCandidate(@Param("candidate") CandidateAggregate candidate);
    int updateCandidate(@Param("candidate") CandidateAggregate candidate,
                        @Param("detectedAt") Instant detectedAt,
                        @Param("similarity") BigDecimal similarity,
                        @Param("cropObjectKey") String cropObjectKey,
                        @Param("frameObjectKey") String frameObjectKey,
                        @Param("boundingBox") String boundingBox);
    void insertDetection(@Param("detection") CandidateEventDetection detection);
    void linkDetectionToCandidate(@Param("id") Long id, @Param("candidateId") Long candidateId);
}
