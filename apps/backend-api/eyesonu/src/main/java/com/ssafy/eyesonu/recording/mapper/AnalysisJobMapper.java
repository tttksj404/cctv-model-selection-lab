package com.ssafy.eyesonu.recording.mapper;

import com.ssafy.eyesonu.recording.domain.AnalysisJob;
import com.ssafy.eyesonu.recording.domain.RecordingAnalysisPublishSnapshot;
import java.util.List;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

@Mapper
public interface AnalysisJobMapper {

    int insert(AnalysisJob job);

    int claimQueued(
            @Param("jobId") Long jobId,
            @Param("workerId") String workerId,
            @Param("leaseSeconds") long leaseSeconds);

    AnalysisJob findRecordingAnalysisById(@Param("jobId") Long jobId);

    AnalysisJob findRecordingAnalysisByIdForUpdate(@Param("jobId") Long jobId);

    RecordingAnalysisPublishSnapshot findRecordingAnalysisPublishSnapshot(
            @Param("jobId") Long jobId, @Param("caseId") Long caseId);

    AnalysisJob findActiveByTarget(
            @Param("caseId") Long caseId,
            @Param("searchConditionId") Long searchConditionId,
            @Param("recordingId") Long recordingId);

    AnalysisJob findById(
            @Param("caseId") Long caseId, @Param("jobId") Long jobId);

    List<AnalysisJob> findRecordingAnalysisByCaseId(@Param("caseId") Long caseId);

    List<AnalysisJob> findRecordingAnalysisByCaseIds(@Param("caseIds") List<Long> caseIds);

    int cancelActive(@Param("caseId") Long caseId, @Param("jobId") Long jobId);

    int retryFailed(@Param("caseId") Long caseId, @Param("jobId") Long jobId);

    int markSucceeded(@Param("caseId") Long caseId, @Param("jobId") Long jobId);
}
