package com.ssafy.eyesonu.camera.mapper;

import com.ssafy.eyesonu.camera.domain.Camera;
import com.ssafy.eyesonu.camera.domain.CameraCreateCommand;
import com.ssafy.eyesonu.camera.domain.CameraHeartbeatState;
import com.ssafy.eyesonu.camera.domain.CameraManagementRow;
import com.ssafy.eyesonu.camera.domain.CameraStreamUrlRow;
import com.ssafy.eyesonu.camera.domain.CameraUpdateCommand;
import java.time.Instant;
import java.util.List;
import java.util.Optional;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

@Mapper
public interface CameraMapper {

    @Select("""
    SELECT id,
           media_server_id AS mediaServerId,
           camera_code AS cameraCode,
           camera_name AS cameraName
    FROM cameras
    WHERE camera_code = #{cameraCode}
    """)
    Optional<Camera> findByCameraCode(@Param("cameraCode") String cameraCode);

    @Select("""
    SELECT id,
           media_server_id AS mediaServerId,
           camera_code AS cameraCode,
           camera_name AS cameraName
    FROM cameras
    WHERE id = #{cameraId}
    """)
    Optional<Camera> findById(@Param("cameraId") Long cameraId);

    @Select("""
    SELECT id,
           media_server_id AS mediaServerId,
           camera_code AS cameraCode,
           camera_name AS cameraName
    FROM cameras
    WHERE camera_code = #{cameraCode}
    FOR UPDATE
    """)
    Optional<Camera> findByCameraCodeForUpdate(@Param("cameraCode") String cameraCode);

    Optional<CameraHeartbeatState> findHeartbeatStateByCameraCode(
            @Param("cameraCode") String cameraCode);

    int updateHeartbeat(
            @Param("cameraId") Long cameraId,
            @Param("mediaServerId") Long mediaServerId,
            @Param("status") String status,
            @Param("lastHeartbeat") Instant lastHeartbeat);

    int markOffline(@Param("threshold") Instant threshold);

    long countAdminCameras(
            @Param("status") String status,
            @Param("search") String search);

    List<CameraManagementRow> findAdminPage(
            @Param("status") String status,
            @Param("search") String search,
            @Param("sortColumn") String sortColumn,
            @Param("sortDirection") String sortDirection,
            @Param("limit") int limit,
            @Param("offset") long offset);

    CameraManagementRow findAdminById(@Param("cameraId") Long cameraId);

    CameraStreamUrlRow findStreamUrlById(@Param("cameraId") Long cameraId);

    CameraManagementRow findAdminByIdForUpdate(@Param("cameraId") Long cameraId);

    int insert(CameraCreateCommand command);

    int updateName(
            @Param("cameraId") Long cameraId,
            @Param("cameraName") String cameraName);

    int updateDetails(CameraUpdateCommand command);
}
