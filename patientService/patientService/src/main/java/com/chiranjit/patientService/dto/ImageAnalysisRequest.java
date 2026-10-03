package com.chiranjit.patientService.dto;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

import java.util.List;

/**
 * One VLM run, posted back for storage by whoever ran it.
 *
 * The agent service is called from the browser rather than from here: a run is
 * minutes of work, and proxying it would mean holding an HTTP request open for
 * that long. The cost of that choice is that this payload is client-supplied,
 * so it is size-bounded and validated rather than trusted.
 *
 * Field names are camelCase, so the caller maps the agent service's snake_case
 * response onto them. That keeps the one-line translation in the caller instead
 * of spreading `@JsonProperty` through this record.
 */
public record ImageAnalysisRequest(

		@NotBlank @Size(max = 20000) String answer,

		@Size(max = 20000) String globalSummary,

		@Size(max = 2000) String question,

		@Size(max = 120) String model,

		@Size(max = 64) String runId,

		Double seconds,

		@Size(max = 64) @Valid List<TileReport> tiles) {

	/** One tile agent's findings. */
	public record TileReport(

			@Size(max = 32) String tileId,

			@Size(max = 20000) String report) {

	}

}
