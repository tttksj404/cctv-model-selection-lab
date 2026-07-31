package com.ssafy.eyesonu.recording.mapper;

import com.ssafy.eyesonu.recording.domain.RecordingAnalysisOutbox;
import java.time.Instant;
import java.util.List;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

@Mapper
public interface RecordingAnalysisOutboxMapper {

    int insert(RecordingAnalysisOutbox outbox);

    List<RecordingAnalysisOutbox> findReady(@Param("limit") int limit);

    int markProcessing(@Param("id") Long id, @Param("claimToken") String claimToken);

    int markPublished(
            @Param("id") Long id,
            @Param("claimToken") String claimToken,
            @Param("publishedAt") Instant publishedAt);

    int markFailed(
            @Param("id") Long id,
            @Param("claimToken") String claimToken,
            @Param("errorMessage") String errorMessage);
}
