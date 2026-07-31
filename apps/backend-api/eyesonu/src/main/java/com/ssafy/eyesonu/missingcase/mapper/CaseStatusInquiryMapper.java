package com.ssafy.eyesonu.missingcase.mapper;

import com.ssafy.eyesonu.common.persistence.mybatis.UtcInstantTypeHandler;
import com.ssafy.eyesonu.missingcase.domain.CaseStatus;
import com.ssafy.eyesonu.missingcase.domain.CaseStatusInquiryRow;
import java.time.Instant;
import java.util.Optional;
import org.apache.ibatis.annotations.Arg;
import org.apache.ibatis.annotations.ConstructorArgs;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

@Mapper
public interface CaseStatusInquiryMapper {

	@ConstructorArgs({
			@Arg(column = "id", javaType = Long.class, id = true),
			@Arg(column = "case_number", javaType = String.class),
			@Arg(column = "status", javaType = CaseStatus.class),
			@Arg(
					column = "reported_at",
					javaType = Instant.class,
					typeHandler = UtcInstantTypeHandler.class),
			@Arg(
					column = "updated_at",
					javaType = Instant.class,
					typeHandler = UtcInstantTypeHandler.class),
			@Arg(
					column = "closed_at",
					javaType = Instant.class,
					typeHandler = UtcInstantTypeHandler.class)
	})
	@Select("""
			SELECT c.id,
			       c.case_number,
			       c.status,
			       c.reported_at,
			       c.updated_at,
			       c.closed_at
			FROM cases c
			JOIN reporters r ON r.id = c.reporter_id
			WHERE c.case_number = #{caseNumber}
			  AND r.phone = #{phone}
			""")
	Optional<CaseStatusInquiryRow> findStatus(
			@Param("caseNumber") String caseNumber,
			@Param("phone") String phone);
}
