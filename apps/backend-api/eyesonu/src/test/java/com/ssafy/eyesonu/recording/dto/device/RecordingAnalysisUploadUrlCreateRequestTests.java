package com.ssafy.eyesonu.recording.dto.device;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import jakarta.validation.Validation;
import jakarta.validation.Validator;
import java.util.List;
import java.util.stream.IntStream;
import org.junit.jupiter.api.Test;

class RecordingAnalysisUploadUrlCreateRequestTests {

    private final Validator validator = Validation.buildDefaultValidatorFactory().getValidator();

    @Test
    void acceptsAtMostOneHundredCandidatesPerRequest() {
        RecordingAnalysisUploadUrlCreateRequest request = requestWithCandidateCount(100);

        assertTrue(validator.validate(request).isEmpty());
    }

    @Test
    void rejectsMoreThanOneHundredCandidatesPerRequest() {
        RecordingAnalysisUploadUrlCreateRequest request = requestWithCandidateCount(101);

        assertFalse(validator.validate(request).isEmpty());
    }

    private RecordingAnalysisUploadUrlCreateRequest requestWithCandidateCount(int count) {
        List<RecordingAnalysisUploadUrlCreateRequest.Candidate> candidates = IntStream.range(0, count)
                .mapToObj(index -> new RecordingAnalysisUploadUrlCreateRequest.Candidate(
                        "track-" + index, "image/jpeg", "image/png"))
                .toList();
        return new RecordingAnalysisUploadUrlCreateRequest(candidates);
    }
}
