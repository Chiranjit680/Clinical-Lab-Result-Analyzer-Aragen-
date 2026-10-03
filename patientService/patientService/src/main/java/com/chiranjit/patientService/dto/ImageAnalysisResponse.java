package com.chiranjit.patientService.dto;

import java.time.Instant;
import java.util.Map;
import java.util.UUID;

/**
 * A stored image analysis. `payload` is the agent service's own response,
 * passed through untouched so the frontend can render a saved analysis with the
 * same component it uses for a live run.
 */
public record ImageAnalysisResponse(

		UUID id,

		UUID imageId,

		String question,

		String answer,

		String model,

		String runId,

		int tileCount,

		Integer durationMs,

		Instant createdAt,

		Map<String, Object> payload) {

}
