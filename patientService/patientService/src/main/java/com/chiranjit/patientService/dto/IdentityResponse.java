package com.chiranjit.patientService.dto;

import java.time.Instant;
import java.time.LocalDate;
import java.util.UUID;

public record IdentityResponse(

		UUID id,

		String fullName,

		LocalDate dateOfBirth,

		String sex,

		String bloodGroup,

		boolean pregnant,

		Instant createdAt,

		Instant updatedAt) {

}
