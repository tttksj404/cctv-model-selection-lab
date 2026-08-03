package com.ssafy.eyesonu.missingcase.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.inOrder;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.ssafy.eyesonu.auth.device.MediaServerPrincipal;
import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.missingcase.dto.device.CandidateEventCreateRequest;
import com.ssafy.eyesonu.missingcase.dto.device.CandidateEventCreateResponse;
import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.List;
import org.springframework.http.HttpStatus;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InOrder;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class CandidateEventSubmissionServiceTests {

    @Mock private CandidateEventAccessValidator accessValidator;
    @Mock private CandidateEventStorageValidator storageValidator;
    @Mock private CandidateEventCommandService commandService;

    @Test
    void verifiesAccessBeforeStorageAndDatabaseCommand() {
        CandidateEventCreateRequest request = request();
        MediaServerPrincipal principal = new MediaServerPrincipal(2L, "media-01");
        CandidateEventCreateResponse expected = new CandidateEventCreateResponse(
                "event-1", 101L, 11L, 1, List.of(9001L), false, null);
        when(commandService.create(principal, request)).thenReturn(expected);
        CandidateEventSubmissionService service = new CandidateEventSubmissionService(
                accessValidator, storageValidator, commandService);

        CandidateEventCreateResponse response = service.create(principal, request);

        assertEquals(expected, response);
        InOrder order = inOrder(accessValidator, storageValidator, commandService);
        order.verify(accessValidator).validateRealtimeAccess(principal, request);
        order.verify(storageValidator).verify(request);
        order.verify(commandService).create(principal, request);
    }

    @Test
    void rejectsUnauthenticatedRequestBeforeStorageAccess() {
        CandidateEventSubmissionService service = new CandidateEventSubmissionService(
                accessValidator, storageValidator, commandService);
        doThrow(new ApiException(HttpStatus.UNAUTHORIZED,
                "AUTHENTICATION_REQUIRED", "Authentication is required"))
                .when(accessValidator).validateRealtimeAccess(null, request());

        assertThrows(ApiException.class, () -> service.create(null, request()));

        verify(accessValidator).validateRealtimeAccess(null, request());
        verify(storageValidator, never()).verify(request());
        verify(commandService, never()).create(null, request());
    }

    @Test
    void rejectsUnissuedObjectKeyBeforeStorageAccess() {
        CandidateEventCreateRequest request = request();
        MediaServerPrincipal principal = new MediaServerPrincipal(2L, "media-01");
        CandidateEventSubmissionService service = new CandidateEventSubmissionService(
                accessValidator, storageValidator, commandService);
        doThrow(new ApiException(HttpStatus.BAD_REQUEST,
                "INVALID_UPLOAD_OBJECT_KEY", "Image object key was not issued"))
                .when(accessValidator).validateRealtimeAccess(principal, request);

        ApiException exception = assertThrows(ApiException.class,
                () -> service.create(principal, request));

        assertEquals("INVALID_UPLOAD_OBJECT_KEY", exception.getCode());
        verify(storageValidator, never()).verify(request);
        verify(commandService, never()).create(principal, request);
    }

    private CandidateEventCreateRequest request() {
        return new CandidateEventCreateRequest(
                101L, "CAM-001", "event-1", OffsetDateTime.parse("2026-08-02T10:00:00Z"),
                "frames/frame.jpg", List.of(new CandidateEventCreateRequest.Detection(
                        "track-1", new BigDecimal("0.91"), "crops/crop.jpg",
                        new CandidateEventCreateRequest.BoundingBox(1, 2, 30, 40))));
    }
}
