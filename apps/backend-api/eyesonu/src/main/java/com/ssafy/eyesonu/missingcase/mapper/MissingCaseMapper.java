package com.ssafy.eyesonu.missingcase.mapper;

import com.ssafy.eyesonu.missingcase.domain.CasePhotoState;
import com.ssafy.eyesonu.missingcase.domain.CaseSortDirection;
import com.ssafy.eyesonu.missingcase.domain.CaseSortField;
import com.ssafy.eyesonu.missingcase.domain.CaseStatus;
import com.ssafy.eyesonu.missingcase.domain.MissingCaseRow;
import com.ssafy.eyesonu.missingcase.domain.ReporterRecord;
import com.ssafy.eyesonu.missingcase.domain.CaseCameraRow;
import com.ssafy.eyesonu.missingcase.domain.SearchConditionRow;
import com.ssafy.eyesonu.missingcase.domain.DeviceSearchTargetRow;
import java.util.Collection;
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

	long countActiveJobsByCondition(
			@Param("caseId") Long caseId, @Param("conditionId") Long conditionId);

	int cancelActiveJobs(@Param("caseId") Long caseId);

	List<SearchConditionRow> findSearchConditions(@Param("caseId") Long caseId);

	SearchConditionRow findSearchCondition(
			@Param("caseId") Long caseId, @Param("conditionId") Long conditionId);

	int insertSearchCondition(SearchConditionRow condition);

	int updateSearchCondition(SearchConditionRow condition);

	int deleteSearchCondition(
			@Param("caseId") Long caseId, @Param("conditionId") Long conditionId);

	List<CaseCameraRow> findCaseCameras(@Param("caseId") Long caseId);

	List<Long> findExistingCameraIds(@Param("cameraIds") Collection<Long> cameraIds);

	int upsertCaseCameras(
			@Param("caseId") Long caseId, @Param("cameraIds") Collection<Long> cameraIds);

	int disableCaseCamera(
			@Param("caseId") Long caseId, @Param("cameraId") Long cameraId);

	List<DeviceSearchTargetRow> findDeviceSearchTargetCameras(@Param("mediaServerId") Long mediaServerId);

	List<DeviceSearchTargetRow> findDeviceSearchTargetConditions(
			@Param("caseIds") Collection<Long> caseIds);
}
