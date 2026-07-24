package com.ssafy.eyesonu.audit.service;

import com.ssafy.eyesonu.audit.mapper.AuditLogMapper;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import tools.jackson.core.JacksonException;
import tools.jackson.databind.ObjectMapper;

@Service
public class AuditService {

	private static final Logger log = LoggerFactory.getLogger(AuditService.class);

	private final AuditLogMapper auditLogMapper;
	private final ObjectMapper objectMapper;

	public AuditService(AuditLogMapper auditLogMapper, ObjectMapper objectMapper) {
		this.auditLogMapper = auditLogMapper;
		this.objectMapper = objectMapper;
	}

	public void recordRequired(
			String actionType,
			Long adminId,
			Long caseId,
			String targetType,
			Long targetId,
			Map<String, ?> detail) {
		auditLogMapper.insert(adminId, caseId, actionType, targetType, targetId, toJson(detail));
	}

	public void recordBestEffort(
			String actionType,
			Long adminId,
			Long caseId,
			String targetType,
			Long targetId,
			Map<String, ?> detail) {
		try {
			recordRequired(actionType, adminId, caseId, targetType, targetId, detail);
		}
		catch (RuntimeException exception) {
			log.warn("Failed to persist audit event: actionType={}", actionType, exception);
		}
	}

	private String toJson(Map<String, ?> detail) {
		try {
			return objectMapper.writeValueAsString(detail == null ? Map.of() : detail);
		}
		catch (JacksonException exception) {
			throw new IllegalArgumentException("Audit detail cannot be serialized", exception);
		}
	}
}
