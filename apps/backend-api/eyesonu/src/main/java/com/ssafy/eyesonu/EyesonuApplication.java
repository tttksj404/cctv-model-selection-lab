package com.ssafy.eyesonu;

import com.ssafy.eyesonu.common.config.RequiredProfileInitializer;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@ConfigurationPropertiesScan
@EnableScheduling
public class EyesonuApplication {

	public static void main(String[] args) {
		SpringApplication application = new SpringApplication(EyesonuApplication.class);
		application.addInitializers(new RequiredProfileInitializer());
		application.run(args);
	}

}
