package com.ssafy.eyesonu.camera.mapper;

import com.ssafy.eyesonu.camera.domain.Camera;
import java.util.Optional;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;

@Mapper
public interface CameraMapper {

    @Select("""
    SELECT id, camera_code AS cameraCode
    FROM cameras
    WHERE camera_code = #{cameraCode}
    """)
    Optional<Camera> findByCameraCode(String cameraCode);
}
