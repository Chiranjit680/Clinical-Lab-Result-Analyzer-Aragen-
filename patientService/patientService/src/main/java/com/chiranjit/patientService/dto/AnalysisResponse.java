package com.chiranjit.patientService.dto;

import com.chiranjit.patientService.entity.ReportStatus;

import java.time.Instant;
import java.util.Map;
import java.util.UUID;

/**
 * A stored analysis. `payload` is the analyzer's own response, passed through
 * untouched so the frontend can render it with the same component it uses for
 * a live run.
 */
public record AnalysisResponse(

		UUID id,

		UUID reportId,

		String threadId,

		ReportStatus status,

		int criticalCount,

		int warningCount,

		int normalCount,

		int unknownCount,

		int errorCount,

		Integer durationMs,

		Instant createdAt,

		Map<String, Object> payload) {

}
