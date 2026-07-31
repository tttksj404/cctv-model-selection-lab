package com.ssafy.eyesonu.admin;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.LinkedHashMap;
import java.util.Map;
import org.flywaydb.core.Flyway;
import org.junit.jupiter.api.Test;
import org.testcontainers.containers.MySQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.utility.DockerImageName;

@Testcontainers(disabledWithoutDocker = true)
class AdminRoleMigrationTests {

	@Container
	private static final MySQLContainer<?> MYSQL =
			new MySQLContainer<>(DockerImageName.parse("mysql:8.0.46"))
					.withDatabaseName("admin_role_migration")
					.withUsername("eyesonu")
					.withPassword("eyesonu_test_password");

	@Test
	void migrationPromotesOnlyTheOldestExistingAdminAndAddsConstraints() throws SQLException {
		Flyway.configure()
				.dataSource(MYSQL.getJdbcUrl(), MYSQL.getUsername(), MYSQL.getPassword())
				.locations("classpath:db/migration")
				.target("6")
				.load()
				.migrate();

		try (Connection connection = connection(); Statement statement = connection.createStatement()) {
			statement.executeUpdate("""
					INSERT INTO admins (id, login_id, password_hash, name)
					VALUES
					(20, 'second', 'hash', 'Second'),
					(10, 'first', 'hash', 'First')
					""");
		}

		flyway().migrate();

		Map<String, String> migrationScripts = new LinkedHashMap<>();
		try (Connection connection = connection();
				Statement statement = connection.createStatement();
				ResultSet result = statement.executeQuery("""
						SELECT version, script
						FROM flyway_schema_history
						WHERE version IN ('6', '7')
						ORDER BY installed_rank
						""")) {
			while (result.next()) {
				migrationScripts.put(result.getString("version"), result.getString("script"));
			}
		}
		assertEquals(
				Map.of(
						"6", "V6__realtime_candidate_event_model.sql",
						"7", "V7__admin_roles_and_status.sql"),
				migrationScripts);

		Map<Long, String> roles = new LinkedHashMap<>();
		try (Connection connection = connection();
				Statement statement = connection.createStatement();
				ResultSet result = statement.executeQuery(
						"SELECT id, role, enabled FROM admins ORDER BY id")) {
			while (result.next()) {
				roles.put(result.getLong("id"), result.getString("role"));
				assertTrue(result.getBoolean("enabled"));
			}
		}

		assertEquals(Map.of(10L, "SUPER_ADMIN", 20L, "ADMIN"), roles);
		try (Connection connection = connection(); Statement statement = connection.createStatement()) {
			assertThrows(SQLException.class, () ->
					statement.executeUpdate("UPDATE admins SET role = 'OWNER' WHERE id = 10"));
			assertThrows(SQLException.class, () ->
					statement.executeUpdate("UPDATE admins SET enabled = 2 WHERE id = 10"));
		}
	}

	private Flyway flyway() {
		return Flyway.configure()
				.dataSource(MYSQL.getJdbcUrl(), MYSQL.getUsername(), MYSQL.getPassword())
				.locations("classpath:db/migration")
				.load();
	}

	private Connection connection() throws SQLException {
		return DriverManager.getConnection(MYSQL.getJdbcUrl(), MYSQL.getUsername(), MYSQL.getPassword());
	}
}
