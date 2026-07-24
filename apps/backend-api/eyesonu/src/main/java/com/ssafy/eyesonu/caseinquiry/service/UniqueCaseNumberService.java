package com.ssafy.eyesonu.caseinquiry.service;

import com.ssafy.eyesonu.caseinquiry.mapper.CaseInquiryMapper;
import org.springframework.stereotype.Service;

@Service
public class UniqueCaseNumberService {

	private static final int MAX_ATTEMPTS = 5;

	private final SecureCaseNumberGenerator generator;
	private final CaseInquiryMapper caseInquiryMapper;

	public UniqueCaseNumberService(
			SecureCaseNumberGenerator generator, CaseInquiryMapper caseInquiryMapper) {
		this.generator = generator;
		this.caseInquiryMapper = caseInquiryMapper;
	}

	public String generate() {
		for (int attempt = 0; attempt < MAX_ATTEMPTS; attempt++) {
			String candidate = generator.generate();
			if (!caseInquiryMapper.existsByCaseNumber(candidate)) {
				return candidate;
			}
		}
		throw new IllegalStateException("Unable to allocate a unique case number");
	}
}
