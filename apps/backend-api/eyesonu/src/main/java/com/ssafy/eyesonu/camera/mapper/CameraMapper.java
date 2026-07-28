package com.ssafy.eyesonu.camera.mapper;

import com.ssafy.eyesonu.camera.domain.Camera;
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
    WHERE camera_code = #{cameraCode}
    FOR UPDATE
    """)
    Optional<Camera> findByCameraCodeForUpdate(@Param("cameraCode") String cameraCode);
}
