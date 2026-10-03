package com.chiranjit.patientService.service;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.core.io.Resource;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;
import org.springframework.web.server.ResponseStatusException;

import java.time.Duration;
import java.util.Map;

/**
 * Calls the Python analyzer service.
 *
 * This is the only place the two back ends talk to each other; everything else
 * about a report stays inside this service.
 */
@Component
public class AnalyzerClient {

	private final RestClient client;

	public AnalyzerClient(@Value("${app.analyzer-base-url:http://127.0.0.1:8000}") String baseUrl,
			@Value("${app.analyzer-timeout-seconds:600}") long timeoutSeconds) {

		SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
		factory.setConnectTimeout(Duration.ofSeconds(15));
		// A full panel routinely takes one to two minutes: every abnormal result
		// is researched before it is explained. The default read timeout would
		// abandon a run that was going to succeed.
		factory.setReadTimeout(Duration.ofSeconds(timeoutSeconds));

		this.client = RestClient.builder().baseUrl(baseUrl).requestFactory(factory).build();
	}

	/**
	 * POSTs the report to /analyze_report and returns the analyzer's response
	 * as-is, so nothing is lost in translation on the way to storage.
	 */
	public Map<String, Object> analyzeReport(Resource file) {
		MultiValueMap<String, Object> parts = new LinkedMultiValueMap<>();
		// The analyzer decides PDF-ness partly from the filename, which the
		// Resource carries, so this must stay a file part rather than raw bytes.
		parts.add("file", file);

		try {
			return this.client.post()
					.uri("/analyze_report")
					.contentType(MediaType.MULTIPART_FORM_DATA)
					.body(parts)
					.retrieve()
					.body(new ParameterizedTypeReference<Map<String, Object>>() {
					});
		}
		catch (RestClientException ex) {
			// Surfaced as 502 rather than 500: the failure is downstream, and
			// saying so makes it obvious where to look.
			throw new ResponseStatusException(HttpStatus.BAD_GATEWAY,
					"The analyzer service could not complete the analysis: " + ex.getMessage(), ex);
		}
	}

}
