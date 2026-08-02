package com.ssafy.eyesonu.missingcase.service;

import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.ssafy.eyesonu.audit.service.AuditService;
import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.missingcase.domain.AdminCandidateRow;
import com.ssafy.eyesonu.missingcase.dto.admin.AdminCandidateReviewRequest;
import com.ssafy.eyesonu.missingcase.mapper.AdminCandidateMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class AdminCandidateReviewServiceTests {

    private static final long CANDIDATE_ID = 11L;
    private static final long ADMIN_ID = 7L;

    @Mock private AdminCandidateMapper mapper;
    @Mock private AdminCandidateQueryService queryService;
    @Mock private AuditService auditService;

    private AdminCandidateReviewService service;

    @BeforeEach
    void setUp() {
        service = new AdminCandidateReviewService(mapper, queryService, auditService);
    }

    @Test
    void rejectsStaleCandidateVersionBeforeUpdating() {
        AdminCandidateRow current = candidate(3L);
        when(mapper.findByIdForUpdate(CANDIDATE_ID)).thenReturn(current);

        assertThrows(ApiException.class, () -> service.review(
                CANDIDATE_ID, new AdminCandidateReviewRequest("CONFIRMED", "확인", 2L), ADMIN_ID));

        verify(mapper, never()).updateReview(any(), any(), any(), any(), any());
        verify(auditService, never()).recordRequired(any(), any(), any(), any(), any(), any());
    }

    @Test
    void rejectsUnsupportedReviewStatus() {
        assertThrows(ApiException.class, () -> service.review(
                CANDIDATE_ID, new AdminCandidateReviewRequest("PENDING", null, 1L), ADMIN_ID));

        verify(mapper, never()).findByIdForUpdate(any());
    }

    private AdminCandidateRow candidate(Long version) {
        AdminCandidateRow row = new AdminCandidateRow();
        row.setId(CANDIDATE_ID);
        row.setCaseId(101L);
        row.setReviewStatus("PENDING");
        row.setVersion(version);
        return row;
    }
}
