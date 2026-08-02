package com.ssafy.eyesonu.missingcase.service;

import com.ssafy.eyesonu.audit.service.AuditService;
import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.missingcase.domain.AdminCandidateRow;
import com.ssafy.eyesonu.missingcase.dto.admin.AdminCandidateDetailResponse;
import com.ssafy.eyesonu.missingcase.dto.admin.AdminCandidateReviewRequest;
import com.ssafy.eyesonu.missingcase.mapper.AdminCandidateMapper;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class AdminCandidateReviewService {
    private final AdminCandidateMapper mapper;
    private final AdminCandidateQueryService queryService;
    private final AuditService auditService;

    public AdminCandidateReviewService(AdminCandidateMapper mapper, AdminCandidateQueryService queryService,
                                       AuditService auditService) {
        this.mapper = mapper;
        this.queryService = queryService;
        this.auditService = auditService;
    }

    @Transactional
    public AdminCandidateDetailResponse review(Long candidateId, AdminCandidateReviewRequest request, Long adminId) {
        String status = normalizeStatus(request.reviewStatus());
        AdminCandidateRow current = mapper.findByIdForUpdate(candidateId);
        if (current == null) throw new ApiException(HttpStatus.NOT_FOUND, "RESOURCE_NOT_FOUND", "Candidate was not found");
        if (!current.getVersion().equals(request.version())) {
            throw new ApiException(HttpStatus.CONFLICT, "OPTIMISTIC_LOCK_CONFLICT", "Candidate has been updated by another administrator.");
        }
        if (mapper.updateReview(candidateId, status, request.reviewComment(), adminId, request.version()) != 1) {
            throw new ApiException(HttpStatus.CONFLICT, "OPTIMISTIC_LOCK_CONFLICT", "Candidate has been updated by another administrator.");
        }
        auditService.recordRequired("CANDIDATE_REVIEWED", adminId, current.getCaseId(), "CANDIDATE", candidateId,
                Map.of("beforeStatus", current.getReviewStatus(), "afterStatus", status));
        return queryService.findById(candidateId);
    }

    private String normalizeStatus(String value) {
        String status = value.trim().toUpperCase(Locale.ROOT);
        if (!List.of("KEPT", "CONFIRMED", "REJECTED").contains(status)) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_ERROR",
                    "reviewStatus must be KEPT, CONFIRMED, or REJECTED");
        }
        return status;
    }
}
