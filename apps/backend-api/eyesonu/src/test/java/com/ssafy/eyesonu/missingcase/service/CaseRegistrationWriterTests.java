package com.ssafy.eyesonu.missingcase.service;

import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyMap;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.ssafy.eyesonu.audit.service.AuditService;
import com.ssafy.eyesonu.missingcase.domain.CaseStatus;
import com.ssafy.eyesonu.missingcase.domain.MissingCaseRow;
import com.ssafy.eyesonu.missingcase.domain.ReporterRecord;
import com.ssafy.eyesonu.missingcase.mapper.MissingCaseMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.dao.DuplicateKeyException;

class CaseRegistrationWriterTests {

	private MissingCaseMapper mapper;
	private AuditService auditService;
	private CaseRegistrationWriter writer;

	@BeforeEach
	void setUp() {
		mapper = mock(MissingCaseMapper.class);
		auditService = mock(AuditService.class);
		writer = new CaseRegistrationWriter(mapper, auditService);
	}

	@Test
	void translatesDuplicateFromCaseInsertToCaseNumberCollision() {
		MissingCaseRow row = row();
		DuplicateKeyException duplicate = new DuplicateKeyException("driver-specific message");
		assignReporterId();
		when(mapper.insertCase(row)).thenThrow(duplicate);

		CaseNumberCollisionException thrown = assertThrows(
				CaseNumberCollisionException.class, () -> writer.write(row, 7L));

		assertSame(duplicate, thrown.getCause());
		verify(auditService, never()).recordRequired(
				anyString(), any(), any(), anyString(), any(), any(), anyMap(), anyMap());
	}

	@Test
	void preservesDuplicateFromReporterInsert() {
		MissingCaseRow row = row();
		DuplicateKeyException duplicate = new DuplicateKeyException("reporter duplicate");
		when(mapper.insertReporter(any(ReporterRecord.class))).thenThrow(duplicate);

		DuplicateKeyException thrown = assertThrows(
				DuplicateKeyException.class, () -> writer.write(row, 7L));

		assertSame(duplicate, thrown);
		verify(mapper, never()).insertCase(any());
	}

	@Test
	void preservesDuplicateFromAuditInsert() {
		MissingCaseRow row = row();
		DuplicateKeyException duplicate = new DuplicateKeyException("audit duplicate");
		assignReporterId();
		doAnswer(invocation -> {
			row.setId(101L);
			return 1;
		}).when(mapper).insertCase(row);
		doThrow(duplicate).when(auditService).recordRequired(
				eq("CASE_CREATED"), eq(7L), eq(101L), eq("CASE"), eq(101L),
				isNull(), anyMap(), anyMap());

		DuplicateKeyException thrown = assertThrows(
				DuplicateKeyException.class, () -> writer.write(row, 7L));

		assertSame(duplicate, thrown);
	}

	private void assignReporterId() {
		doAnswer(invocation -> {
			invocation.getArgument(0, ReporterRecord.class).setId(100L);
			return 1;
		}).when(mapper).insertReporter(any(ReporterRecord.class));
	}

	private MissingCaseRow row() {
		MissingCaseRow row = new MissingCaseRow();
		row.setReporterName("Reporter");
		row.setReporterPhone("01012345678");
		row.setCaseNumber("EFU-TEST");
		row.setStatus(CaseStatus.RECEIVED);
		return row;
	}
}
