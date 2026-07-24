package com.ssafy.eyesonu.caseinquiry.mapper;

import java.time.LocalDateTime;
import java.util.Optional;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;

@Mapper
public interface CaseInquiryMapper {

	@Select("""
			SELECT c.id,
			       c.case_number AS caseNumber,
			       c.status,
			       c.reported_at AS reportedAt,
			       c.updated_at AS updatedAt,
			       c.closed_at AS closedAt
			FROM cases c
			JOIN reporters r ON r.id = c.reporter_id
			WHERE c.case_number = #{caseNumber}
			  AND r.phone = #{phone}
			""")
	Optional<CaseStatusRow> findStatus(String caseNumber, String phone);

	@Select("SELECT EXISTS(SELECT 1 FROM cases WHERE case_number = #{caseNumber})")
	boolean existsByCaseNumber(String caseNumber);

	record CaseStatusRow(
			Long id,
			String caseNumber,
			String status,
			LocalDateTime reportedAt,
			LocalDateTime updatedAt,
			LocalDateTime closedAt) {
	}
}
