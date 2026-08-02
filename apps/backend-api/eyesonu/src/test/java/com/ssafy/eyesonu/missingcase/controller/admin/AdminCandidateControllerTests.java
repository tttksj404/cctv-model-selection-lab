package com.ssafy.eyesonu.missingcase.controller.admin;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.ssafy.eyesonu.missingcase.service.AdminCandidatePageResult;
import com.ssafy.eyesonu.missingcase.service.AdminCandidateQueryService;
import com.ssafy.eyesonu.missingcase.service.AdminCandidateReviewService;
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

    @Mock
    private AdminCandidateReviewService reviewService;

    @Test
    void returnsFreshSignedUrlsWithoutCachingCandidatePage() {
        when(queryService.findAll(any())).thenReturn(
                new AdminCandidatePageResult(List.of(), 0, 20, 0, 0, "lastDetectedAt,desc"));
        AdminCandidateController controller = new AdminCandidateController(queryService, reviewService);

        ResponseEntity<?> response = controller.findAll(null, null, null, null, null,
                0, 20, "lastDetectedAt,desc");

        assertEquals(HttpStatus.OK, response.getStatusCode());
        assertEquals("no-store", response.getHeaders().getCacheControl());
        verify(queryService).findAll(any());
    }
}
