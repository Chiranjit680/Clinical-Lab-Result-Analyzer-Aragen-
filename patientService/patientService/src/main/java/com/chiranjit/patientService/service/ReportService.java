package com.chiranjit.patientService.service;

import com.chiranjit.patientService.dto.ReportRequest;
import com.chiranjit.patientService.dto.ReportResponse;
import com.chiranjit.patientService.entity.Identity;
import com.chiranjit.patientService.entity.LabReport;
import com.chiranjit.patientService.entity.ReportStatus;
import com.chiranjit.patientService.repository.IdentityRepository;
import com.chiranjit.patientService.repository.LabReportRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.server.ResponseStatusException;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

@Service
@RequiredArgsConstructor
public class ReportService {

	private final LabReportRepository labReportRepository;

	private final IdentityRepository identityRepository;

	private final StorageService storageService;

	public ReportResponse saveReport(ReportRequest request) {
		LabReport report = new LabReport();
		report.setPatient(getPatientOrThrow(request.getPatientId()));
		report.setReportPath(request.getReportPath());
		report.setStatus(request.getStatus());
		report.setCreatedAt(Instant.now());

		return toResponse(labReportRepository.save(report));
	}

	/**
	 * Stores an uploaded file and records it against the patient in one step.
	 * The patient is resolved first so an unknown id fails before anything is
	 * written to disk, which would otherwise leave an orphaned file behind.
	 */
	public ReportResponse saveUploadedReport(MultipartFile file, UUID patientId, ReportStatus status) {
		Identity patient = getPatientOrThrow(patientId);

		LabReport report = new LabReport();
		report.setPatient(patient);
		report.setReportPath(storageService.store(file));
		report.setStatus(status);
		report.setCreatedAt(Instant.now());

		return toResponse(labReportRepository.save(report));
	}

	public StorageService.StoredFile loadReportFile(UUID reportId) {
		return storageService.load(getReportOrThrow(reportId).getReportPath());
	}

	public ReportResponse getReportById(UUID reportId) {
		return toResponse(getReportOrThrow(reportId));
	}

	public List<ReportResponse> getAllReportsByPatientId(UUID patientId) {
		getPatientOrThrow(patientId);
		return labReportRepository.findByPatientIdOrderByCreatedAtDesc(patientId).stream().map(this::toResponse)
				.toList();
	}

	public ReportResponse updateReportStatus(UUID reportId, ReportStatus status) {
		LabReport report = getReportOrThrow(reportId);
		report.setStatus(status);

		return toResponse(labReportRepository.save(report));
	}

	public void deleteReport(UUID reportId) {
		labReportRepository.delete(getReportOrThrow(reportId));
	}

	private LabReport getReportOrThrow(UUID reportId) {
		return labReportRepository.findById(reportId).orElseThrow(
				() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Report not found: " + reportId));
	}

	private Identity getPatientOrThrow(UUID patientId) {
		return identityRepository.findById(patientId).orElseThrow(
				() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Patient not found: " + patientId));
	}

	private ReportResponse toResponse(LabReport report) {
		return new ReportResponse(report.getId(), report.getPatient().getId(), report.getReportPath(),
				report.getStatus(), report.getCreatedAt());
	}

}
