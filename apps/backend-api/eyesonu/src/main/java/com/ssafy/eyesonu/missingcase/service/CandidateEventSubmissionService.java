package com.ssafy.eyesonu.missingcase.service;

import com.ssafy.eyesonu.auth.device.MediaServerPrincipal;
import com.ssafy.eyesonu.missingcase.dto.device.CandidateEventCreateRequest;
import com.ssafy.eyesonu.missingcase.dto.device.CandidateEventCreateResponse;
import org.springframework.stereotype.Service;

@Service
public class CandidateEventSubmissionService {

    private final CandidateEventAccessValidator accessValidator;
    private final CandidateEventStorageValidator storageValidator;
    private final CandidateEventCommandService commandService;

    public CandidateEventSubmissionService(
            CandidateEventAccessValidator accessValidator,
            CandidateEventStorageValidator storageValidator,
            CandidateEventCommandService commandService) {
        this.accessValidator = accessValidator;
        this.storageValidator = storageValidator;
        this.commandService = commandService;
    }

    public CandidateEventCreateResponse create(
            MediaServerPrincipal principal,
            CandidateEventCreateRequest request) {
        accessValidator.validateRealtimeAccess(principal, request);
        storageValidator.verify(request);
        return commandService.create(principal, request);
    }
}
