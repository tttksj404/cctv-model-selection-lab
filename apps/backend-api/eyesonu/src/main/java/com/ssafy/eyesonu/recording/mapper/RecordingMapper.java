package com.ssafy.eyesonu.recording.mapper;

import com.ssafy.eyesonu.recording.domain.Recording;
import com.ssafy.eyesonu.recording.domain.UploadStatus;
import java.time.LocalDateTime;
import java.util.List;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

@Mapper
public interface RecordingMapper {

    int insert(Recording recording);

    Recording findById(@Param("id") Long id);

    Recording findByS3Key(@Param("s3Key") String s3Key);

    List<Recording> findAll(
            @Param("cameraId") Long cameraId,
            @Param("uploadStatus") UploadStatus uploadStatus,
            @Param("startFrom") LocalDateTime startFrom,
            @Param("startTo") LocalDateTime startTo);

    int updateUploadStatusAndFileSize(
            @Param("id") Long id,
            @Param("uploadStatus") UploadStatus uploadStatus,
            @Param("fileSize") Long fileSize);
}
