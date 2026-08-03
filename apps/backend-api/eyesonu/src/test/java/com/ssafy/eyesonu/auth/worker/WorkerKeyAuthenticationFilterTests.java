package com.ssafy.eyesonu.auth.worker;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

import com.ssafy.eyesonu.auth.security.SecurityErrorWriter;
import jakarta.servlet.FilterChain;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.security.core.context.SecurityContextHolder;

class WorkerKeyAuthenticationFilterTests {

    @AfterEach
    void clearContext() {
        SecurityContextHolder.clearContext();
    }

    @Test
    void authenticatesValidWorkerKey() throws Exception {
        SecurityErrorWriter errors = mock(SecurityErrorWriter.class);
        FilterChain chain = mock(FilterChain.class);
        MockHttpServletRequest request = new MockHttpServletRequest();
        request.addHeader(WorkerKeyAuthenticationFilter.HEADER_NAME, "secret-key");
        MockHttpServletResponse response = new MockHttpServletResponse();
        WorkerKeyAuthenticationFilter filter = new WorkerKeyAuthenticationFilter(
                "secret-key", "recording-worker-1", errors);

        filter.doFilter(request, response, chain);

        Object principal = SecurityContextHolder.getContext().getAuthentication().getPrincipal();
        WorkerPrincipal worker = assertInstanceOf(WorkerPrincipal.class, principal);
        assertEquals("recording-worker-1", worker.workerId());
        verify(chain).doFilter(request, response);
    }

    @Test
    void rejectsInvalidWorkerKey() throws Exception {
        SecurityErrorWriter errors = mock(SecurityErrorWriter.class);
        FilterChain chain = mock(FilterChain.class);
        MockHttpServletRequest request = new MockHttpServletRequest();
        request.addHeader(WorkerKeyAuthenticationFilter.HEADER_NAME, "wrong-key");
        MockHttpServletResponse response = new MockHttpServletResponse();
        WorkerKeyAuthenticationFilter filter = new WorkerKeyAuthenticationFilter(
                "secret-key", "recording-worker-1", errors);

        filter.doFilter(request, response, chain);

        verify(errors).write(response, 401, "INVALID_WORKER_KEY", "A valid Worker Key is required.");
    }
}
