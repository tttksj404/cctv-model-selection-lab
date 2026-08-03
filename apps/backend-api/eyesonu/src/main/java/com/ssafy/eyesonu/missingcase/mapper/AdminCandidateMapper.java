package com.ssafy.eyesonu.missingcase.mapper;

import com.ssafy.eyesonu.missingcase.domain.AdminCandidateDetectionRow;
import com.ssafy.eyesonu.missingcase.domain.AdminCandidateRow;
import java.time.Instant;
import java.util.List;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

@Mapper
public interface AdminCandidateMapper {
    long countCandidates(@Param("caseId") Long caseId, @Param("cameraId") Long cameraId,
                         @Param("reviewStatus") String reviewStatus,
                         @Param("detectedFrom") Instant detectedFrom, @Param("detectedTo") Instant detectedTo);

    List<AdminCandidateRow> findPage(@Param("caseId") Long caseId, @Param("cameraId") Long cameraId,
                                     @Param("reviewStatus") String reviewStatus,
                                     @Param("detectedFrom") Instant detectedFrom, @Param("detectedTo") Instant detectedTo,
                                     @Param("sortField") String sortField, @Param("sortDirection") String sortDirection,
                                     @Param("limit") int limit, @Param("offset") long offset);

    AdminCandidateRow findById(@Param("id") Long id);
    AdminCandidateRow findByIdForUpdate(@Param("id") Long id);
    int updateReview(@Param("id") Long id, @Param("reviewStatus") String reviewStatus,
                     @Param("reviewComment") String reviewComment, @Param("adminId") Long adminId,
                     @Param("version") Long version);
    List<AdminCandidateDetectionRow> findDetections(@Param("candidateId") Long candidateId);
}
