package com.ssafy.eyesonu.caseinquiry.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import com.ssafy.eyesonu.caseinquiry.mapper.CaseInquiryMapper;
import org.junit.jupiter.api.Test;

class UniqueCaseNumberServiceTests {

	@Test
	void retriesWhenGeneratedNumberAlreadyExists() {
		SecureCaseNumberGenerator generator = mock(SecureCaseNumberGenerator.class);
		CaseInquiryMapper mapper = mock(CaseInquiryMapper.class);
		String duplicate = "EFU-0123456789ABCDEFGHJKMNPQRS";
		String available = "EFU-1123456789ABCDEFGHJKMNPQRS";
		when(generator.generate()).thenReturn(duplicate, available);
		when(mapper.existsByCaseNumber(duplicate)).thenReturn(true);
		when(mapper.existsByCaseNumber(available)).thenReturn(false);

		assertEquals(available, new UniqueCaseNumberService(generator, mapper).generate());
	}
}
