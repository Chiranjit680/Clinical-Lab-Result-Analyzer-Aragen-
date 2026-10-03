package com.chiranjit.patientService.dto;

import com.chiranjit.patientService.entity.ReportStatus;
import lombok.AllArgsConstructor;
import lombok.Data;

import java.time.Instant;
import java.util.UUID;

@Data
@AllArgsConstructor
public class ReportResponse {

	private UUID id;

	private UUID patientId;

	private String reportPath;

	private ReportStatus status;

	private Instant createdAt;

	/**
	 * Whether a stored analysis exists for this report. Derived from the
	 * relationship rather than kept as its own column, so it cannot drift out
	 * of step with reality.
	 */
	private boolean analysisAvailable;

	/** Id of that analysis, or null when there is none. */
	private UUID analysisId;

}
