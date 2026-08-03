package com.ssafy.eyesonu.recording.mapper;

import com.ssafy.eyesonu.recording.domain.RecordingAnalysisResult;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

@Mapper
public interface RecordingAnalysisResultMapper {
    RecordingAnalysisResult findByJobId(@Param("jobId") Long jobId);
    int insert(RecordingAnalysisResult result);
}
