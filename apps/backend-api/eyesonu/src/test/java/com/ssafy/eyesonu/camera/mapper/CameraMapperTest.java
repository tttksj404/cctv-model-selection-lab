package com.ssafy.eyesonu.camera.mapper;

import static org.assertj.core.api.Assertions.assertThat;
import static org.junit.jupiter.api.Assertions.assertEquals;

import com.ssafy.eyesonu.camera.domain.CameraCreateCommand;
import com.ssafy.eyesonu.camera.domain.CameraManagementRow;
import com.ssafy.eyesonu.camera.domain.CameraUpdateCommand;
import java.math.BigDecimal;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.test.context.jdbc.SqlConfig;
import org.testcontainers.containers.MySQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.utility.DockerImageName;
import org.springframework.transaction.annotation.Transactional;

@SpringBootTest(properties = "spring.flyway.enabled=true")
@ActiveProfiles("test")
@Testcontainers(disabledWithoutDocker = true)
@Transactional
@Sql(
        scripts = "/recording-fixture.sql",
        config = @SqlConfig(transactionMode = SqlConfig.TransactionMode.INFERRED))
class CameraMapperTest {

    @Container
    @ServiceConnection
    static final MySQLContainer<?> MYSQL = new MySQLContainer<>(
            DockerImageName.parse("mysql:8.0.46"))
            .withDatabaseName("eyesonu_camera_test")
            .withUsername("eyesonu")
            .withPassword("eyesonu_test_password");

    @DynamicPropertySource
    static void properties(DynamicPropertyRegistry registry) {
        registry.add("spring.flyway.enabled", () -> true);
    }

    @Autowired
    private CameraMapper cameraMapper;

    @Test
    void adminLookupJoinsMediaServerAndKeepsInternalRtspValueAvailableToService() {
        CameraManagementRow row = cameraMapper.findAdminById(153001L);

        assertThat(row).isNotNull();
        assertThat(row.mediaServerId()).isEqualTo(152001L);
        assertThat(row.mediaServerCode()).isEqualTo("recording-fixture-server-1");
        assertThat(row.cameraCode()).isEqualTo("recording-fixture-camera-153001");
        assertThat(row.rtspUrl()).isEqualTo("rtsp://recording-fixture/153001/stream");
        assertThat(cameraMapper.findAdminByIdForUpdate(153001L).cameraCode())
                .isEqualTo(row.cameraCode());
    }

    @Test
    void adminPageFiltersAndUsesStableAllowedSort() {
        List<CameraManagementRow> rows = cameraMapper.findAdminPage(
                "OFFLINE", "15300", "camera_code", "ASC", 20, 0);

        assertThat(rows).extracting(CameraManagementRow::cameraCode)
                .containsExactly(
                        "recording-fixture-camera-153001",
                        "recording-fixture-camera-153002");
        assertEquals(2L, cameraMapper.countAdminCameras("OFFLINE", "fixture"));
    }

    @Test
    void insertAndUpdateKeepImmutableAndOperationalFieldsOutsideUpdateCommand() {
        CameraCreateCommand create = new CameraCreateCommand(
                152001L,
                "camera-mapper-created",
                "Created Camera",
                new BigDecimal("37.5000000"),
                new BigDecimal("127.0000000"),
                "Created Address",
                "rtsp://created/stream");
        assertEquals(1, cameraMapper.insert(create));
        assertThat(create.getId()).isPositive();

        CameraManagementRow created = cameraMapper.findAdminById(create.getId());
        assertThat(created.status()).isEqualTo("OFFLINE");
        assertThat(created.lastHeartbeat()).isNull();

        assertEquals(1, cameraMapper.updateDetails(new CameraUpdateCommand(
                create.getId(),
                152002L,
                "Updated Camera",
                new BigDecimal("37.6000000"),
                new BigDecimal("127.1000000"),
                "Updated Address",
                "rtsp://updated/stream")));
        CameraManagementRow updated = cameraMapper.findAdminById(create.getId());
        assertThat(updated.cameraCode()).isEqualTo("camera-mapper-created");
        assertThat(updated.status()).isEqualTo("OFFLINE");
        assertThat(updated.lastHeartbeat()).isNull();
        assertThat(updated.mediaServerId()).isEqualTo(152002L);
    }
}
