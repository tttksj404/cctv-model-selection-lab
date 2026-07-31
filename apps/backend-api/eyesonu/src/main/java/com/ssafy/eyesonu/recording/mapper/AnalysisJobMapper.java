package com.ssafy.eyesonu.recording.mapper;

import com.ssafy.eyesonu.recording.domain.AnalysisJob;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface AnalysisJobMapper {

    int insert(AnalysisJob job);

    AnalysisJob findActiveByTarget(
            Long caseId, Long searchConditionId, Long recordingId);

    AnalysisJob findById(Long caseId, Long jobId);
}
