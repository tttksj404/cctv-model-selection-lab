package com.ssafy.eyesonu.recording.mapper;

import com.ssafy.eyesonu.recording.domain.AnalysisJob;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import java.util.List;

@Mapper
public interface AnalysisJobMapper {

    int insert(AnalysisJob job);

    int claimQueued(Long jobId);

    AnalysisJob findRecordingAnalysisById(@Param("jobId") Long jobId);

    AnalysisJob findActiveByTarget(
            @Param("caseId") Long caseId,
            @Param("searchConditionId") Long searchConditionId,
            @Param("recordingId") Long recordingId);

    AnalysisJob findById(
            @Param("caseId") Long caseId, @Param("jobId") Long jobId);

    List<AnalysisJob> findRecordingAnalysisByCaseId(@Param("caseId") Long caseId);

    int cancelActive(@Param("caseId") Long caseId, @Param("jobId") Long jobId);

    int retryFailed(@Param("caseId") Long caseId, @Param("jobId") Long jobId);
}
