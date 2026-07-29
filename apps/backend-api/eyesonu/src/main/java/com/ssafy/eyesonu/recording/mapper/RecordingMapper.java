package com.ssafy.eyesonu.recording.mapper;

import com.ssafy.eyesonu.recording.domain.AdminRecordingRow;
import com.ssafy.eyesonu.recording.domain.Recording;
import com.ssafy.eyesonu.recording.domain.RecordingRegistration;
import com.ssafy.eyesonu.recording.domain.RecordingRegistrationResult;
import com.ssafy.eyesonu.recording.domain.RecordingSortDirection;
import com.ssafy.eyesonu.recording.domain.RecordingSortField;
import java.time.Instant;
import java.util.List;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

@Mapper
public interface RecordingMapper {

    int insert(Recording recording);

    Recording findById(@Param("id") Long id);

    Recording findByS3Key(@Param("s3Key") String s3Key);

    int insertRegistration(RecordingRegistration registration);

    RecordingRegistrationResult findRegistrationByKey(
            @Param("mediaServerId") Long mediaServerId,
            @Param("idempotencyKey") String idempotencyKey);

    long countAdminRecordings(
            @Param("cameraId") Long cameraId,
            @Param("startFrom") Instant startFrom,
            @Param("startTo") Instant startTo);

    List<AdminRecordingRow> findAdminPage(
            @Param("cameraId") Long cameraId,
            @Param("startFrom") Instant startFrom,
            @Param("startTo") Instant startTo,
            @Param("sortField") RecordingSortField sortField,
            @Param("sortDirection") RecordingSortDirection sortDirection,
            @Param("limit") int limit,
            @Param("offset") long offset);

    AdminRecordingRow findAdminDetail(@Param("id") Long id);
}
