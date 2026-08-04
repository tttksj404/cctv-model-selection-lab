package com.ssafy.eyesonu.common.web;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

@Component
public class NoStoreResponseFilter extends OncePerRequestFilter {

	@Override
	protected void doFilterInternal(
			HttpServletRequest request,
			HttpServletResponse response,
			FilterChain filterChain) throws ServletException, IOException {
		String uri = request.getRequestURI();
		if (uri.startsWith("/api/v1/auth/")
				|| uri.startsWith("/api/v1/admins")
				|| (uri.startsWith("/api/v1/device/cameras/")
						&& uri.endsWith("/recording-upload-urls"))
				|| uri.equals("/api/v1/cases/status-inquiries")) {
			response.setHeader("Cache-Control", "no-store");
		}
		filterChain.doFilter(request, response);
	}
}
