package com.ssafy.eyesonu.recording.mapper;

import static org.assertj.core.api.Assertions.assertThat;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;

import com.ssafy.eyesonu.recording.domain.Recording;
import com.ssafy.eyesonu.recording.domain.UploadStatus;
import java.sql.SQLException;
import java.time.LocalDateTime;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.function.Executable;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.dao.DataAccessException;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.test.context.jdbc.Sql.ExecutionPhase;
import org.springframework.test.context.jdbc.SqlConfig;
import org.springframework.transaction.annotation.Transactional;

@SpringBootTest
@ActiveProfiles("test")
@Transactional
@Sql(
        scripts = "/recording-fixture.sql",
        executionPhase = ExecutionPhase.BEFORE_TEST_METHOD,
        config = @SqlConfig(transactionMode = SqlConfig.TransactionMode.INFERRED))
class RecordingMapperTest {

    private static final Long CAMERA_ID = 153001L;
    private static final Long OTHER_CAMERA_ID = 153002L;
    private static final LocalDateTime BASE_TIME = LocalDateTime.of(2026, 7, 23, 9, 0);

    @Autowired
    private RecordingMapper recordingMapper;

    @Test
    void insertPopulatesGeneratedId() {
        Recording recording = recording("insert-key", BASE_TIME, 100L, UploadStatus.PENDING);

        assertEquals(1, recordingMapper.insert(recording));
        assertThat(recording.getId()).isPositive();
    }

    @Test
    void findByIdReturnsRecording() {
        Recording inserted = insert("find-by-id-key", BASE_TIME);

        Recording found = recordingMapper.findById(inserted.getId());

        assertThat(found.getId()).isEqualTo(inserted.getId());
        assertThat(found.getCameraId()).isEqualTo(CAMERA_ID);
        assertThat(found.getStartTime()).isEqualTo(BASE_TIME);
        assertThat(found.getUploadStatus()).isEqualTo(UploadStatus.PENDING);
    }

    @Test
    void findByS3KeyReturnsRecording() {
        Recording inserted = insert("find-by-s3-key", BASE_TIME);

        Recording found = recordingMapper.findByS3Key("find-by-s3-key");

        assertThat(found.getId()).isEqualTo(inserted.getId());
        assertThat(found.getS3Key()).isEqualTo("find-by-s3-key");
    }

    @Test
    void findByIdReturnsNullWhenIdDoesNotExist() {
        assertNull(recordingMapper.findById(Long.MAX_VALUE));
    }

    @Test
    void findAllFiltersByCameraId() {
        Recording matching = insert("camera-filter-match", BASE_TIME);
        Recording otherCamera = recording("camera-filter-other", BASE_TIME.plusHours(1), 100L, UploadStatus.PENDING);
        otherCamera.setCameraId(OTHER_CAMERA_ID);
        assertEquals(1, recordingMapper.insert(otherCamera));

        List<Recording> result = recordingMapper.findAll(CAMERA_ID, null, null, null);

        assertThat(result).hasSize(1);
        assertThat(result.get(0).getCameraId()).isEqualTo(CAMERA_ID);
        assertThat(result.get(0).getS3Key()).isEqualTo(matching.getS3Key());
    }

    @Test
    void findAllFiltersByUploadStatus() {
        insert("status-pending", BASE_TIME);
        Recording completed = recording("status-completed", BASE_TIME.plusHours(1), 100L, UploadStatus.COMPLETED);
        recordingMapper.insert(completed);

        List<Recording> result = recordingMapper.findAll(null, UploadStatus.COMPLETED, null, null);

        assertThat(result).extracting(Recording::getS3Key).containsExactly("status-completed");
    }

    @Test
    void findAllFiltersFromStartTime() {
        insert("before-start-filter", BASE_TIME);
        insert("after-start-filter", BASE_TIME.plusHours(2));

        List<Recording> result = recordingMapper.findAll(null, null, BASE_TIME.plusHours(1), null);

        assertThat(result).extracting(Recording::getS3Key).containsExactly("after-start-filter");
    }

    @Test
    void findAllFiltersToStartTime() {
        insert("before-end-filter", BASE_TIME);
        insert("after-end-filter", BASE_TIME.plusHours(2));

        List<Recording> result = recordingMapper.findAll(null, null, null, BASE_TIME.plusHours(1));

        assertThat(result).extracting(Recording::getS3Key).containsExactly("before-end-filter");
    }

    @Test
    void findAllAppliesAllFilters() {
        insert("composite-match", BASE_TIME.plusHours(1));
        insert("composite-status-mismatch", BASE_TIME.plusHours(1));
        Recording mismatch = recording("composite-time-mismatch", BASE_TIME.plusHours(3), 100L, UploadStatus.COMPLETED);
        recordingMapper.insert(mismatch);
        recordingMapper.updateUploadStatusAndFileSize(
                recordingMapper.findByS3Key("composite-status-mismatch").getId(),
                UploadStatus.COMPLETED,
                100L);

        List<Recording> result = recordingMapper.findAll(
                CAMERA_ID,
                UploadStatus.PENDING,
                BASE_TIME,
                BASE_TIME.plusHours(2));

        assertThat(result).extracting(Recording::getS3Key).containsExactly("composite-match");
    }

    @Test
    void findAllReturnsStartTimeDescendingWhenNoFilterExists() {
        insert("sort-old", BASE_TIME);
        insert("sort-new", BASE_TIME.plusHours(2));
        insert("sort-middle", BASE_TIME.plusHours(1));

        List<Recording> result = recordingMapper.findAll(null, null, null, null);

        assertThat(result).extracting(Recording::getS3Key)
                .containsExactly("sort-new", "sort-middle", "sort-old");
    }

    @Test
    void updateUploadStatusAndFileSizeUpdatesFields() {
        Recording inserted = insert("update-key", BASE_TIME);

        assertEquals(1, recordingMapper.updateUploadStatusAndFileSize(
                inserted.getId(), UploadStatus.COMPLETED, 999L));

        Recording updated = recordingMapper.findById(inserted.getId());
        assertThat(updated.getUploadStatus()).isEqualTo(UploadStatus.COMPLETED);
        assertThat(updated.getFileSize()).isEqualTo(999L);
    }

    @Test
    void updateReturnsZeroWhenIdDoesNotExist() {
        assertEquals(0, recordingMapper.updateUploadStatusAndFileSize(
                Long.MAX_VALUE, UploadStatus.COMPLETED, 1L));
    }

    @Test
    void duplicateS3KeyViolatesUniqueConstraint() {
        insert("duplicate-key", BASE_TIME);

        assertThrows(DataIntegrityViolationException.class,
                () -> insert("duplicate-key", BASE_TIME.plusHours(1)));
    }

    @Test
    void nonexistentCameraViolatesForeignKeyConstraint() {
        Recording recording = recording("missing-camera", BASE_TIME, 100L, UploadStatus.PENDING);
        recording.setCameraId(Long.MAX_VALUE);

        assertThrows(DataIntegrityViolationException.class, () -> recordingMapper.insert(recording));
    }

    @Test
    void negativeFileSizeViolatesCheckConstraint() {
        assertCheckConstraintViolation(
                "ck_recordings_file_size",
                () -> recordingMapper.insert(recording("negative-size", BASE_TIME, -1L, UploadStatus.PENDING)));
    }

    @Test
    void reversedTimeRangeViolatesCheckConstraint() {
        Recording recording = recording("reversed-time", BASE_TIME.plusHours(1), 100L, UploadStatus.PENDING);
        recording.setEndTime(BASE_TIME);

        assertCheckConstraintViolation("ck_recordings_time_range", () -> recordingMapper.insert(recording));
    }

    private void assertCheckConstraintViolation(String constraintName, Executable operation) {
        DataAccessException exception = assertThrows(DataAccessException.class, operation);

        assertThat(exception.getRootCause()).isInstanceOf(SQLException.class);
        assertThat(exception.getMessage()).contains(constraintName);
        assertThat(exception.getRootCause().getMessage()).contains(constraintName);
    }

    private Recording insert(String s3Key, LocalDateTime startTime) {
        Recording recording = recording(s3Key, startTime, 100L, UploadStatus.PENDING);
        assertEquals(1, recordingMapper.insert(recording));
        return recording;
    }

    private Recording recording(String s3Key, LocalDateTime startTime, Long fileSize, UploadStatus uploadStatus) {
        return new Recording(
                null,
                CAMERA_ID,
                startTime,
                startTime.plusMinutes(1),
                s3Key,
                fileSize,
                uploadStatus,
                null);
    }
}
