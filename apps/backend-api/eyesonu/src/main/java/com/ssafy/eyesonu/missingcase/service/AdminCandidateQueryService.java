package com.ssafy.eyesonu.missingcase.service;

import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.missingcase.domain.AdminCandidateDetectionRow;
import com.ssafy.eyesonu.missingcase.domain.AdminCandidateRow;
import com.ssafy.eyesonu.missingcase.dto.admin.AdminCandidateDetailResponse;
import com.ssafy.eyesonu.missingcase.dto.admin.AdminCandidateDetectionResponse;
import com.ssafy.eyesonu.missingcase.dto.admin.AdminCandidateListResponse;
import com.ssafy.eyesonu.missingcase.dto.admin.AdminCandidateSearchCondition;
import com.ssafy.eyesonu.missingcase.mapper.AdminCandidateMapper;
import com.ssafy.eyesonu.storage.StorageObjectUrlSigner;
import java.time.Instant;
import java.util.List;
import java.util.Locale;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;

@Service
public class AdminCandidateQueryService {
    private final AdminCandidateMapper mapper;
    private final StorageObjectUrlSigner urlSigner;

    public AdminCandidateQueryService(AdminCandidateMapper mapper, StorageObjectUrlSigner urlSigner) {
        this.mapper = mapper;
        this.urlSigner = urlSigner;
    }

    public AdminCandidatePageResult findAll(AdminCandidateSearchCondition condition) {
        validatePage(condition.page(), condition.size());
        String[] sort = parseSort(condition.sort());
        String reviewStatus = normalizeStatus(condition.reviewStatus());
        Instant from = condition.detectedFrom() == null ? null : condition.detectedFrom().toInstant();
        Instant to = condition.detectedTo() == null ? null : condition.detectedTo().toInstant();
        if (from != null && to != null && !from.isBefore(to)) {
            throw validation("detectedFrom must be before detectedTo");
        }
        long total = mapper.countCandidates(condition.caseId(), condition.cameraId(), reviewStatus, from, to);
        List<AdminCandidateListResponse> candidates = total == 0 ? List.of() : mapper.findPage(
                        condition.caseId(), condition.cameraId(), reviewStatus, from, to,
                        sort[0], sort[1], condition.size(), (long) condition.page() * condition.size())
                .stream().map(this::toListResponse).toList();
        long pages = total / condition.size() + (total % condition.size() == 0 ? 0 : 1);
        return new AdminCandidatePageResult(candidates, condition.page(), condition.size(), total,
                (int) Math.min(Integer.MAX_VALUE, pages), sort[0] + "," + sort[1]);
    }

    public AdminCandidateDetailResponse findById(Long candidateId) {
        AdminCandidateRow candidate = mapper.findById(candidateId);
        if (candidate == null) {
            throw new ApiException(HttpStatus.NOT_FOUND, "RESOURCE_NOT_FOUND", "Candidate was not found");
        }
        List<AdminCandidateDetectionResponse> detections = mapper.findDetections(candidateId).stream()
                .map(this::toDetectionResponse).toList();
        return AdminCandidateDetailResponse.from(candidate,
                sign(candidate.getFrameObjectKey()), sign(candidate.getCropObjectKey()), detections);
    }

    private AdminCandidateListResponse toListResponse(AdminCandidateRow row) {
        return AdminCandidateListResponse.from(row, sign(row.getCropObjectKey()));
    }

    private AdminCandidateDetectionResponse toDetectionResponse(AdminCandidateDetectionRow row) {
        return AdminCandidateDetectionResponse.from(row, sign(row.getCropObjectKey()));
    }

    private String sign(String objectKey) {
        return objectKey == null ? null : urlSigner.createGetUrl(objectKey);
    }

    private String normalizeStatus(String value) {
        if (value == null || value.isBlank()) return null;
        String status = value.trim().toUpperCase(Locale.ROOT);
        if (!status.equals("PENDING") && !status.equals("KEPT")
                && !status.equals("CONFIRMED") && !status.equals("REJECTED")) {
            throw validation("reviewStatus must be PENDING, KEPT, CONFIRMED, or REJECTED");
        }
        return status;
    }

    private String[] parseSort(String value) {
        String normalized = value == null || value.isBlank() ? "lastDetectedAt,desc" : value;
        String[] parts = normalized.split(",", -1);
        if (parts.length != 2
                || (!parts[0].equals("lastDetectedAt") && !parts[0].equals("firstDetectedAt")
                && !parts[0].equals("bestSimilarity") && !parts[0].equals("createdAt"))
                || (!parts[1].equals("asc") && !parts[1].equals("desc"))) {
            throw validation("sort must be one of lastDetectedAt, firstDetectedAt, bestSimilarity, createdAt with asc or desc");
        }
        return parts;
    }

    private void validatePage(int page, int size) {
        if (page < 0 || size < 1 || size > 100) throw validation("page must be at least 0 and size must be between 1 and 100");
    }

    private ApiException validation(String message) {
        return new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_ERROR", message);
    }
}
