package com.ssafy.eyesonu.admin.mapper;

import com.ssafy.eyesonu.admin.domain.Admin;
import java.util.Optional;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Options;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

@Mapper
public interface AdminMapper {

	@Select("""
			SELECT id, login_id AS loginId, password_hash AS passwordHash, name
			FROM admins
			WHERE login_id = #{loginId}
			""")
	Optional<Admin> findByLoginId(String loginId);

	@Select("""
			SELECT id, login_id AS loginId, password_hash AS passwordHash, name
			FROM admins
			WHERE id = #{id}
			""")
	Optional<Admin> findById(Long id);

	@Select("SELECT COUNT(*) FROM admins")
	long count();

	@Insert("""
			INSERT INTO admins (login_id, password_hash, name)
			VALUES (#{loginId}, #{passwordHash}, #{name})
			""")
	@Options(useGeneratedKeys = true, keyProperty = "id")
	void insert(AdminInsertCommand command);

	@Update("UPDATE admins SET name = #{name} WHERE id = #{id}")
	int updateName(@Param("id") Long id, @Param("name") String name);

	@Update("UPDATE admins SET password_hash = #{passwordHash} WHERE id = #{id}")
	int updatePassword(@Param("id") Long id, @Param("passwordHash") String passwordHash);

	class AdminInsertCommand {
		private Long id;
		private final String loginId;
		private final String passwordHash;
		private final String name;

		public AdminInsertCommand(String loginId, String passwordHash, String name) {
			this.loginId = loginId;
			this.passwordHash = passwordHash;
			this.name = name;
		}

		public Long getId() {
			return id;
		}

		public void setId(Long id) {
			this.id = id;
		}

		public String getLoginId() {
			return loginId;
		}

		public String getPasswordHash() {
			return passwordHash;
		}

		public String getName() {
			return name;
		}
	}
}
