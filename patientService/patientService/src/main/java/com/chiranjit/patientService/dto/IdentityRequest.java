package com.chiranjit.patientService.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.PastOrPresent;
import jakarta.validation.constraints.Size;

import java.time.LocalDate;

public record IdentityRequest(

		@NotBlank @Size(max = 120) String fullName,

		@NotNull @PastOrPresent LocalDate dateOfBirth,

		@NotBlank @Size(max = 10) String sex,

		@Size(max = 5) String bloodGroup,

		Boolean pregnant) {

}
