package com.chiranjit.patientService.dto;

import com.chiranjit.patientService.entity.ReportStatus;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.UUID;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class ReportRequest {

	@NotNull
	private UUID patientId;

	@NotBlank
	@Size(max = 500)
	private String reportPath;

	@NotNull
	private ReportStatus status;

}
