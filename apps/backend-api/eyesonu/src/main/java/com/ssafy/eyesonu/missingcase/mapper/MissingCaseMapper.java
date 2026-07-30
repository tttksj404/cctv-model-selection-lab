package com.ssafy.eyesonu.missingcase.mapper;

import com.ssafy.eyesonu.missingcase.domain.CasePhotoState;
import com.ssafy.eyesonu.missingcase.domain.CaseSortDirection;
import com.ssafy.eyesonu.missingcase.domain.CaseSortField;
import com.ssafy.eyesonu.missingcase.domain.CaseStatus;
import com.ssafy.eyesonu.missingcase.domain.MissingCaseRow;
import com.ssafy.eyesonu.missingcase.domain.ReporterRecord;
import java.time.Instant;
import java.util.List;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

@Mapper
public interface MissingCaseMapper {

	int insertReporter(ReporterRecord reporter);

	int insertCase(MissingCaseRow missingCase);

	MissingCaseRow findById(@Param("id") Long id);

	MissingCaseRow findByIdForUpdate(@Param("id") Long id);

	CasePhotoState findPhotoState(@Param("id") Long id);

	CasePhotoState findPhotoStateForUpdate(@Param("id") Long id);

	long countCases(
			@Param("status") CaseStatus status,
			@Param("caseNumber") String caseNumber,
			@Param("missingName") String missingName,
			@Param("reportedFrom") Instant reportedFrom,
			@Param("reportedTo") Instant reportedTo);

	List<MissingCaseRow> findPage(
			@Param("status") CaseStatus status,
			@Param("caseNumber") String caseNumber,
			@Param("missingName") String missingName,
			@Param("reportedFrom") Instant reportedFrom,
			@Param("reportedTo") Instant reportedTo,
			@Param("sortField") CaseSortField sortField,
			@Param("sortDirection") CaseSortDirection sortDirection,
			@Param("limit") int limit,
			@Param("offset") long offset);

	int updateReporter(MissingCaseRow missingCase);

	int updateCase(MissingCaseRow missingCase);

	int updateStatus(
			@Param("id") Long id,
			@Param("status") CaseStatus status,
			@Param("closedAt") Instant closedAt);

	int updatePhoto(@Param("id") Long id, @Param("photoS3Key") String photoS3Key);

	long countSearchConditions(@Param("caseId") Long caseId);

	long countActiveCameras(@Param("caseId") Long caseId);

	long countPendingCandidates(@Param("caseId") Long caseId);

	long countActiveJobs(@Param("caseId") Long caseId);

	int cancelActiveJobs(@Param("caseId") Long caseId);
}
