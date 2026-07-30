package com.ssafy.eyesonu.missingcase.service;

import com.ssafy.eyesonu.audit.service.AuditService;
import com.ssafy.eyesonu.missingcase.domain.MissingCaseRow;
import com.ssafy.eyesonu.missingcase.domain.ReporterRecord;
import com.ssafy.eyesonu.missingcase.mapper.MissingCaseMapper;
import java.util.Map;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

@Component
public class CaseRegistrationWriter {

	private final MissingCaseMapper mapper;
	private final AuditService auditService;

	public CaseRegistrationWriter(MissingCaseMapper mapper, AuditService auditService) {
		this.mapper = mapper;
		this.auditService = auditService;
	}

	/**
	 * Runs one case-number allocation attempt in an independent transaction. A successful
	 * registration remains committed even if a caller's surrounding transaction later rolls back.
	 */
	@Transactional(propagation = Propagation.REQUIRES_NEW)
	public MissingCaseRow write(MissingCaseRow missingCase, Long adminId) {
		ReporterRecord reporter = new ReporterRecord(
				null, missingCase.getReporterName(), missingCase.getReporterPhone(),
				missingCase.getReporterEmail(), missingCase.getReporterRelation());
		mapper.insertReporter(reporter);
		missingCase.setReporterId(reporter.getId());
		try {
			// reporterId was allocated above, so the only expected duplicate at this boundary
			// under the current schema is the generated case number.
			mapper.insertCase(missingCase);
		}
		catch (DuplicateKeyException exception) {
			throw new CaseNumberCollisionException(exception);
		}
		auditService.recordRequired(
				"CASE_CREATED", adminId, missingCase.getId(), "CASE", missingCase.getId(),
				null,
				CaseAuditValues.snapshot(missingCase),
				Map.of("caseNumber", missingCase.getCaseNumber()));
		return mapper.findById(missingCase.getId());
	}
}
