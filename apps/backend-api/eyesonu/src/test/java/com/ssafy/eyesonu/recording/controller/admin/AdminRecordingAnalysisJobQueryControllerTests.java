package com.ssafy.eyesonu.recording.controller.admin;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.ssafy.eyesonu.recording.service.RecordingAnalysisJobService;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.HttpStatus;

@ExtendWith(MockitoExtension.class)
class AdminRecordingAnalysisJobQueryControllerTests {

    @Mock
    private RecordingAnalysisJobService service;

    @Test
    void delegatesDashboardJobLookupToBulkService() {
        List<Long> caseIds = List.of(101L, 202L);
        when(service.findAllForDashboard(caseIds)).thenReturn(List.of());
        AdminRecordingAnalysisJobQueryController controller =
                new AdminRecordingAnalysisJobQueryController(service);

        var response = controller.findAllForDashboard(caseIds);

        assertEquals(HttpStatus.OK, response.getStatusCode());
        verify(service).findAllForDashboard(caseIds);
    }
}
