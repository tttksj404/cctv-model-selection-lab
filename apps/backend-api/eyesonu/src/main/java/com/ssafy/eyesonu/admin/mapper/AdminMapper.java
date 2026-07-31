package com.ssafy.eyesonu.admin.mapper;

import com.ssafy.eyesonu.admin.domain.Admin;
import com.ssafy.eyesonu.admin.domain.AdminRole;
import java.util.List;
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
			SELECT id, login_id AS loginId, password_hash AS passwordHash, name,
			       role, enabled, created_at AS createdAt
			FROM admins
			WHERE login_id = #{loginId}
			""")
	Optional<Admin> findByLoginId(String loginId);

	@Select("""
			SELECT id, login_id AS loginId, password_hash AS passwordHash, name,
			       role, enabled, created_at AS createdAt
			FROM admins
			WHERE id = #{id}
			""")
	Optional<Admin> findById(Long id);

	@Select("""
			SELECT id, login_id AS loginId, password_hash AS passwordHash, name,
			       role, enabled, created_at AS createdAt
			FROM admins
			ORDER BY created_at DESC, id DESC
			""")
	List<Admin> findAll();

	@Select("SELECT EXISTS(SELECT 1 FROM admins WHERE login_id = #{loginId})")
	boolean existsByLoginId(String loginId);

	@Select("""
			SELECT id, login_id AS loginId, password_hash AS passwordHash, name,
			       role, enabled, created_at AS createdAt
			FROM admins
			WHERE id = #{id}
			FOR UPDATE
			""")
	Optional<Admin> findByIdForUpdate(Long id);

	@Select("""
			SELECT id
			FROM admins
			WHERE role = 'SUPER_ADMIN' AND enabled = TRUE
			ORDER BY id
			FOR UPDATE
			""")
	List<Long> findActiveSuperAdminIdsForUpdate();

	@Select("SELECT COUNT(*) FROM admins")
	long count();

	@Insert("""
			INSERT INTO admins (login_id, password_hash, name, role, enabled)
			VALUES (#{loginId}, #{passwordHash}, #{name}, #{role}, #{enabled})
			""")
	@Options(useGeneratedKeys = true, keyProperty = "id")
	void insert(AdminInsertCommand command);

	@Update("UPDATE admins SET name = #{name} WHERE id = #{id}")
	int updateName(@Param("id") Long id, @Param("name") String name);

	@Update("UPDATE admins SET password_hash = #{passwordHash} WHERE id = #{id}")
	int updatePassword(@Param("id") Long id, @Param("passwordHash") String passwordHash);

	@Update("UPDATE admins SET enabled = #{enabled} WHERE id = #{id}")
	int updateEnabled(@Param("id") Long id, @Param("enabled") boolean enabled);

	class AdminInsertCommand {
		private Long id;
		private final String loginId;
		private final String passwordHash;
		private final String name;
		private final AdminRole role;
		private final boolean enabled;

		public AdminInsertCommand(String loginId, String passwordHash, String name) {
			this(loginId, passwordHash, name, AdminRole.ADMIN, true);
		}

		public AdminInsertCommand(
				String loginId,
				String passwordHash,
				String name,
				AdminRole role,
				boolean enabled) {
			this.loginId = loginId;
			this.passwordHash = passwordHash;
			this.name = name;
			this.role = role;
			this.enabled = enabled;
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

		public AdminRole getRole() {
			return role;
		}

		public boolean isEnabled() {
			return enabled;
		}
	}
}
