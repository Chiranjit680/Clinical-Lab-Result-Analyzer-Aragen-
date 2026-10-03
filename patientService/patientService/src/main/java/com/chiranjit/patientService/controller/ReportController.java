package com.chiranjit.patientService.controller;

import com.chiranjit.patientService.dto.AnalysisResponse;
import com.chiranjit.patientService.dto.EmailReportRequest;
import com.chiranjit.patientService.dto.ReportRequest;
import com.chiranjit.patientService.dto.ReportResponse;
import com.chiranjit.patientService.entity.ReportStatus;
import com.chiranjit.patientService.service.ReportService;
import com.chiranjit.patientService.service.StorageService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.core.io.Resource;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RequestPart;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;
import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/api/reports")
@RequiredArgsConstructor
public class ReportController {

	private final ReportService reportService;

	/** Records a report that already exists somewhere, by path. */
	@PostMapping("/save")
	@ResponseStatus(HttpStatus.CREATED)
	public ReportResponse saveReport(@Valid @RequestBody ReportRequest request) {
		return reportService.saveReport(request);
	}

	/**
	 * Uploads the report file itself. The stored path is generated server-side,
	 * so callers never choose where the file lands.
	 */
	@PostMapping(value = "/upload", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
	@ResponseStatus(HttpStatus.CREATED)
	public ReportResponse uploadReport(@RequestPart("file") MultipartFile file,
			@RequestParam("patientId") UUID patientId,
			@RequestParam(value = "status", defaultValue = "NORMAL") ReportStatus status) {
		return reportService.saveUploadedReport(file, patientId, status);
	}

	@GetMapping("/download/{reportId}")
	public ResponseEntity<Resource> downloadReport(@PathVariable UUID reportId) {
		StorageService.StoredFile stored = reportService.loadReportFile(reportId);

		return ResponseEntity.ok()
				.contentType(MediaType.parseMediaType(stored.contentType()))
				.header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"" + stored.filename() + "\"")
				.body(stored.resource());
	}

	/**
	 * Analyses a stored report and saves the result against it, replacing any
	 * previous analysis. Runs for one to two minutes.
	 */
	@PostMapping("/{reportId}/analyze")
	public AnalysisResponse analyzeReport(@PathVariable UUID reportId) {
		return reportService.analyzeReport(reportId);
	}

	/** Emails the report, with its latest analysis rendered into the body. */
	@PostMapping("/{reportId}/email")
	public Map<String, String> emailReport(@PathVariable UUID reportId,
			@Valid @RequestBody EmailReportRequest request) {
		reportService.emailReport(reportId, request.to(), request.note());
		return Map.of("status", "sent", "to", request.to());
	}

	/** The stored analysis for a report, or 404 when none has been run. */
	@GetMapping("/{reportId}/analysis")
	public AnalysisResponse getAnalysis(@PathVariable UUID reportId) {
		return reportService.getAnalysis(reportId);
	}

	@GetMapping("/get/{reportId}")
	public ReportResponse getReport(@PathVariable UUID reportId) {
		return reportService.getReportById(reportId);
	}

	@GetMapping("/getall/{patientId}")
	public List<ReportResponse> getAllReports(@PathVariable UUID patientId) {
		return reportService.getAllReportsByPatientId(patientId);
	}

	@PutMapping("/updateStatus/{reportId}/{status}")
	public ReportResponse updateReportStatus(@PathVariable UUID reportId, @PathVariable ReportStatus status) {
		return reportService.updateReportStatus(reportId, status);
	}

	@DeleteMapping("/delete/{reportId}")
	@ResponseStatus(HttpStatus.NO_CONTENT)
	public void deleteReport(@PathVariable UUID reportId) {
		reportService.deleteReport(reportId);
	}

}
