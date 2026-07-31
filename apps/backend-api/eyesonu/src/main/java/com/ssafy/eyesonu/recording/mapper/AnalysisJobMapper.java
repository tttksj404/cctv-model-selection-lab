package com.ssafy.eyesonu.recording.mapper;

import com.ssafy.eyesonu.recording.domain.AnalysisJob;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

@Mapper
public interface AnalysisJobMapper {

    int insert(AnalysisJob job);

    AnalysisJob findActiveByTarget(
            @Param("caseId") Long caseId,
            @Param("searchConditionId") Long searchConditionId,
            @Param("recordingId") Long recordingId);

    AnalysisJob findById(
            @Param("caseId") Long caseId, @Param("jobId") Long jobId);
}
