package com.ssafy.eyesonu.missingcase.controller.admin;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.ssafy.eyesonu.missingcase.service.AdminCandidatePageResult;
import com.ssafy.eyesonu.missingcase.service.AdminCandidateQueryService;
import java.time.Instant;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;

@ExtendWith(MockitoExtension.class)
class AdminCandidateControllerTests {

    @Mock
    private AdminCandidateQueryService queryService;

    @Test
    void returnsNotModifiedWithoutLoadingCandidatePageWhenEtagMatches() {
        Instant updatedAt = Instant.parse("2026-07-30T04:00:00Z");
        when(queryService.findLastModified()).thenReturn(updatedAt);
        when(queryService.findAll(any())).thenReturn(
                new AdminCandidatePageResult(List.of(), 0, 20, 0, 0, "lastDetectedAt,desc"));
        AdminCandidateController controller = new AdminCandidateController(queryService);

        ResponseEntity<?> first = controller.findAll(null, null, null, null, null,
                0, 20, "lastDetectedAt,desc", null);
        ResponseEntity<?> unchanged = controller.findAll(null, null, null, null, null,
                0, 20, "lastDetectedAt,desc", first.getHeaders().getETag());

        assertEquals(HttpStatus.OK, first.getStatusCode());
        assertNotNull(first.getHeaders().getETag());
        assertEquals(HttpStatus.NOT_MODIFIED, unchanged.getStatusCode());
        assertEquals(first.getHeaders().getETag(), unchanged.getHeaders().getETag());
        verify(queryService, times(2)).findLastModified();
        verify(queryService, times(1)).findAll(any());
    }
}
