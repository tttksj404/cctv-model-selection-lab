package com.ssafy.eyesonu.audit.mapper;

import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

@Mapper
public interface AuditLogMapper {

	default void insert(
			Long adminId,
			Long caseId,
			String actionType,
			String targetType,
			Long targetId,
			String detail) {
		insert(adminId, caseId, actionType, targetType, targetId, null, null, detail);
	}

	@Insert("""
			INSERT INTO audit_logs
			(admin_id, case_id, action_type, target_type, target_id,
			 before_value, after_value, detail)
			VALUES
			(#{adminId}, #{caseId}, #{actionType}, #{targetType}, #{targetId},
			 CAST(#{beforeValue} AS JSON), CAST(#{afterValue} AS JSON), #{detail})
			""")
	void insert(
			@Param("adminId") Long adminId,
			@Param("caseId") Long caseId,
			@Param("actionType") String actionType,
			@Param("targetType") String targetType,
			@Param("targetId") Long targetId,
			@Param("beforeValue") String beforeValue,
			@Param("afterValue") String afterValue,
			@Param("detail") String detail);
}
