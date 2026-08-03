package com.ssafy.eyesonu.auth.worker;

import com.ssafy.eyesonu.auth.security.SecurityErrorWriter;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.List;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContext;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.filter.OncePerRequestFilter;

public class WorkerKeyAuthenticationFilter extends OncePerRequestFilter {

    public static final String HEADER_NAME = "X-Worker-Key";
    private static final SimpleGrantedAuthority AUTHORITY = new SimpleGrantedAuthority("ROLE_AI_WORKER");

    private final byte[] expectedKey;
    private final String workerId;
    private final SecurityErrorWriter errors;

    public WorkerKeyAuthenticationFilter(String expectedKey, String workerId, SecurityErrorWriter errors) {
        this.expectedKey = expectedKey == null ? new byte[0] : expectedKey.getBytes(StandardCharsets.UTF_8);
        this.workerId = workerId;
        this.errors = errors;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain filterChain)
            throws ServletException, IOException {
        String provided = request.getHeader(HEADER_NAME);
        byte[] providedBytes = provided == null ? new byte[0] : provided.getBytes(StandardCharsets.UTF_8);
        if (expectedKey.length == 0 || !MessageDigest.isEqual(expectedKey, providedBytes)) {
            errors.write(response, 401, "INVALID_WORKER_KEY", "A valid Worker Key is required.");
            return;
        }

        UsernamePasswordAuthenticationToken authentication = new UsernamePasswordAuthenticationToken(
                new WorkerPrincipal(workerId), null, List.of(AUTHORITY));
        SecurityContext context = SecurityContextHolder.createEmptyContext();
        context.setAuthentication(authentication);
        SecurityContextHolder.setContext(context);
        filterChain.doFilter(request, response);
    }
}
