package com.chiranjit.patientService.dto;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/**
 * Who to send a report to, and an optional line of context from the sender.
 */
public record EmailReportRequest(

		@NotBlank @Email @Size(max = 254) String to,

		@Size(max = 2000) String note) {

}
