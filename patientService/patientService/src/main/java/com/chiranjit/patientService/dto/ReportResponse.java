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

}
