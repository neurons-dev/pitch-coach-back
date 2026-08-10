package com.pitchcoach.core;

import java.util.Locale;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class CoreServiceApplication {

	public static void main(String[] args) {
		Locale.setDefault(Locale.KOREA);
		SpringApplication.run(CoreServiceApplication.class, args);
	}

}
