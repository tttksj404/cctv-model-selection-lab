package com.ssafy.eyesonu;

import static org.junit.jupiter.api.Assertions.assertEquals;

import com.ssafy.eyesonu.common.config.properties.MinioProperties;
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
	private MinioProperties minioProperties;

	@Test
	void contextLoads() {
		assertEquals("eyesonu-test", minioProperties.getBucket());
		assertEquals("ap-northeast-2", minioProperties.getRegion());
	}

}
