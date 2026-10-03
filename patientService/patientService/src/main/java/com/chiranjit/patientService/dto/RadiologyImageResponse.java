package com.chiranjit.patientService.dto;

import com.chiranjit.patientService.entity.Modality;

import java.time.Instant;
import java.util.UUID;

public record RadiologyImageResponse(

		UUID id,

		UUID patientId,

		String imagePath,

		Modality modality,

		String bodyPart,

		String description,

		Instant createdAt,

		/**
		 * Whether a VLM analysis is stored for this image. Lets a listing show
		 * which images have been analysed without fetching every payload.
		 */
		boolean analysisAvailable,

		/** Null when no analysis is stored. */
		UUID analysisId) {

}
