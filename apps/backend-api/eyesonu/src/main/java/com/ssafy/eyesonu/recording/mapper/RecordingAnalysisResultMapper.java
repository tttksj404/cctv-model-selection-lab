package com.ssafy.eyesonu.recording.mapper;

import com.ssafy.eyesonu.recording.domain.RecordingAnalysisResult;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

@Mapper
public interface RecordingAnalysisResultMapper {
    RecordingAnalysisResult findByJobIdAndAttempt(
            @Param("jobId") Long jobId, @Param("attempt") int attempt);
    int insert(RecordingAnalysisResult result);
}
