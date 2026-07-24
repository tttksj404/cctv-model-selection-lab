package com.ssafy.eyesonu.audit.mapper;

import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

@Mapper
public interface AuditLogMapper {

	@Insert("""
			INSERT INTO audit_logs
			(admin_id, case_id, action_type, target_type, target_id, detail)
			VALUES
			(#{adminId}, #{caseId}, #{actionType}, #{targetType}, #{targetId}, #{detail})
			""")
	void insert(
			@Param("adminId") Long adminId,
			@Param("caseId") Long caseId,
			@Param("actionType") String actionType,
			@Param("targetType") String targetType,
			@Param("targetId") Long targetId,
			@Param("detail") String detail);
}
