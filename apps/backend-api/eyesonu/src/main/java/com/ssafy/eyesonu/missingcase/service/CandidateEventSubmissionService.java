package com.ssafy.eyesonu.missingcase.service;

import com.ssafy.eyesonu.auth.device.MediaServerPrincipal;
import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.missingcase.dto.device.CandidateEventCreateRequest;
import com.ssafy.eyesonu.missingcase.dto.device.CandidateEventCreateResponse;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;

@Service
public class CandidateEventSubmissionService {

    private final CandidateEventStorageValidator storageValidator;
    private final CandidateEventCommandService commandService;

    public CandidateEventSubmissionService(
            CandidateEventStorageValidator storageValidator,
            CandidateEventCommandService commandService) {
        this.storageValidator = storageValidator;
        this.commandService = commandService;
    }

    public CandidateEventCreateResponse create(
            MediaServerPrincipal principal,
            CandidateEventCreateRequest request) {
        if (principal == null || principal.mediaServerId() == null) {
            throw new ApiException(HttpStatus.UNAUTHORIZED,
                    "AUTHENTICATION_REQUIRED", "Authentication is required");
        }
        storageValidator.verify(request);
        return commandService.create(principal, request);
    }
}
