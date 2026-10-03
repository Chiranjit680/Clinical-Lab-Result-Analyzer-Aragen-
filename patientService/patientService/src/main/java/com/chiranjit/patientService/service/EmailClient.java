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
import tools.jackson.core.JacksonException;
import tools.jackson.databind.ObjectMapper;

import java.time.Duration;
import java.util.Map;

/**
 * Calls the Python email service.
 *
 * That service holds the Gmail credential and owns nothing else: it has no
 * database and no access to the uploads folder, so everything it needs — the
 * file and the analysis — is sent with the request.
 */
@Component
public class EmailClient {

	private final RestClient client;

	private final ObjectMapper objectMapper;

	public EmailClient(@Value("${app.email-service-base-url:http://127.0.0.1:8083}") String baseUrl,
			@Value("${app.email-timeout-seconds:60}") long timeoutSeconds, ObjectMapper objectMapper) {

		this.objectMapper = objectMapper;

		SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
		factory.setConnectTimeout(Duration.ofSeconds(10));
		// Sending is quick; only the first call is slow, when the service has to
		// complete its OAuth handshake.
		factory.setReadTimeout(Duration.ofSeconds(timeoutSeconds));

		this.client = RestClient.builder().baseUrl(baseUrl).requestFactory(factory).build();
	}

	/**
	 * Sends one report, with its analysis rendered into the body by the email
	 * service. `analysis` may be null — a report that has never been analysed is
	 * still worth sharing.
	 */
	public void sendReport(Resource file, String to, String patientName, Map<String, Object> analysis, String note) {
		MultiValueMap<String, Object> parts = new LinkedMultiValueMap<>();
		parts.add("file", file);
		parts.add("to", to);
		if (patientName != null) {
			parts.add("patient_name", patientName);
		}
		if (note != null && !note.isBlank()) {
			parts.add("note", note);
		}
		if (analysis != null) {
			parts.add("analysis_json", writeJson(analysis));
		}

		try {
			this.client.post()
					.uri("/send_report")
					.contentType(MediaType.MULTIPART_FORM_DATA)
					.body(parts)
					.retrieve()
					.body(new ParameterizedTypeReference<Map<String, Object>>() {
					});
		}
		catch (RestClientException ex) {
			// 502 rather than 500: the failure is downstream, and saying so makes
			// it obvious whether to look here or at the email service.
			throw new ResponseStatusException(HttpStatus.BAD_GATEWAY,
					"The email service could not send the report: " + ex.getMessage(), ex);
		}
	}

	/**
	 * Sends one radiological image, with its stored VLM analysis rendered into
	 * the body. `analysis` may be null — an image that has never been analysed is
	 * still worth sharing.
	 */
	public void sendImage(Resource file, String to, String patientName, String caption,
			Map<String, Object> analysis, String note) {

		MultiValueMap<String, Object> parts = new LinkedMultiValueMap<>();
		parts.add("file", file);
		parts.add("to", to);
		if (patientName != null) {
			parts.add("patient_name", patientName);
		}
		// "Chest X-ray", say: the modality and body part, which the email service
		// has no other way to know.
		if (caption != null && !caption.isBlank()) {
			parts.add("caption", caption);
		}
		if (note != null && !note.isBlank()) {
			parts.add("note", note);
		}
		if (analysis != null) {
			parts.add("analysis_json", writeJson(analysis));
		}

		try {
			this.client.post()
					.uri("/send_image")
					.contentType(MediaType.MULTIPART_FORM_DATA)
					.body(parts)
					.retrieve()
					.body(new ParameterizedTypeReference<Map<String, Object>>() {
					});
		}
		catch (RestClientException ex) {
			throw new ResponseStatusException(HttpStatus.BAD_GATEWAY,
					"The email service could not send the image: " + ex.getMessage(), ex);
		}
	}

	private String writeJson(Map<String, Object> analysis) {
		try {
			return this.objectMapper.writeValueAsString(analysis);
		}
		// Jackson 3 made these unchecked, so this catch is a deliberate choice
		// to report a storage problem rather than let it surface as a bare 500.
		catch (JacksonException ex) {
			throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR,
					"Could not serialise the stored analysis", ex);
		}
	}

}
