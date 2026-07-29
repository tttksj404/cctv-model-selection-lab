package com.ssafy.eyesonu.missingcase.service;

import com.ssafy.eyesonu.audit.service.AuditService;
import com.ssafy.eyesonu.missingcase.domain.MissingCaseRow;
import com.ssafy.eyesonu.missingcase.domain.ReporterRecord;
import com.ssafy.eyesonu.missingcase.mapper.MissingCaseMapper;
import java.util.Map;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

@Component
public class CaseRegistrationWriter {

	private final MissingCaseMapper mapper;
	private final AuditService auditService;

	public CaseRegistrationWriter(MissingCaseMapper mapper, AuditService auditService) {
		this.mapper = mapper;
		this.auditService = auditService;
	}

	@Transactional
	public MissingCaseRow write(MissingCaseRow missingCase, Long adminId) {
		ReporterRecord reporter = new ReporterRecord(
				null, missingCase.getReporterName(), missingCase.getReporterPhone(),
				missingCase.getReporterEmail(), missingCase.getReporterRelation());
		mapper.insertReporter(reporter);
		missingCase.setReporterId(reporter.getId());
		mapper.insertCase(missingCase);
		auditService.recordRequired(
				"CASE_CREATED", adminId, missingCase.getId(), "CASE", missingCase.getId(),
				null,
				CaseAuditValues.snapshot(missingCase),
				Map.of("caseNumber", missingCase.getCaseNumber()));
		return mapper.findById(missingCase.getId());
	}
}
