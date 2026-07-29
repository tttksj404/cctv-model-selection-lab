package com.ssafy.eyesonu;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.ssafy.eyesonu.common.config.properties.S3Properties;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.ActiveProfiles;

@ActiveProfiles("test")
@SpringBootTest(useMainMethod = SpringBootTest.UseMainMethod.ALWAYS)
@Import(TestDatabaseConfiguration.class)
class EyesonuApplicationTests {

	@Autowired
	private S3Properties s3Properties;

	@Test
	void contextLoads() {
		assertEquals("eyesonu-test", s3Properties.getBucket());
		assertEquals("ap-northeast-2", s3Properties.getRegion());
		assertTrue(s3Properties.isPathStyleAccess());
	}

}
