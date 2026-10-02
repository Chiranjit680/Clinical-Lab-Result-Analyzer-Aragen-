package com.chiranjit.patientService.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/**
 * Without this, the browser blocks every call from the Vite dev server to this
 * service, since they are different origins.
 *
 * The allowed origins are configurable because the launcher moves the frontend
 * to another port when 5173 is taken; a hard-coded origin would then reject
 * every request with no obvious cause.
 */
@Configuration
public class WebConfig implements WebMvcConfigurer {

	@Value("${app.cors-origins:http://localhost:5173,http://127.0.0.1:5173}")
	private String[] corsOrigins;

	@Override
	public void addCorsMappings(CorsRegistry registry) {
		registry.addMapping("/api/**")
				.allowedOrigins(corsOrigins)
				.allowedMethods("GET", "POST", "PUT", "DELETE", "OPTIONS")
				.allowedHeaders("*");
	}

}
