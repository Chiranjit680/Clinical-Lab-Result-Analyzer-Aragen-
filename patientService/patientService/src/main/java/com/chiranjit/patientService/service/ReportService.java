package com.chiranjit.patientService.service;

import com.chiranjit.patientService.dto.AnalysisResponse;
import com.chiranjit.patientService.dto.ReportRequest;
import com.chiranjit.patientService.dto.ReportResponse;
import com.chiranjit.patientService.entity.Analysis;
import com.chiranjit.patientService.entity.Identity;
import com.chiranjit.patientService.entity.LabReport;
import com.chiranjit.patientService.entity.ReportStatus;
import com.chiranjit.patientService.repository.AnalysisRepository;
import com.chiranjit.patientService.repository.IdentityRepository;
import com.chiranjit.patientService.repository.LabReportRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.server.ResponseStatusException;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.function.Function;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class ReportService {

	private final LabReportRepository labReportRepository;

	private final IdentityRepository identityRepository;

	private final StorageService storageService;

	private final AnalysisRepository analysisRepository;

	private final AnalyzerClient analyzerClient;

	private final EmailClient emailClient;

	public ReportResponse saveReport(ReportRequest request) {
		LabReport report = new LabReport();
		report.setPatient(getPatientOrThrow(request.getPatientId()));
		report.setReportPath(request.getReportPath());
		report.setStatus(request.getStatus());
		report.setCreatedAt(Instant.now());

		return toResponse(labReportRepository.save(report), null);
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

		return toResponse(labReportRepository.save(report), null);
	}

	/**
	 * Sends a stored report to the analyzer and saves the result against it.
	 *
	 * Deliberately not wrapped in a transaction: the analyzer call takes one to
	 * two minutes, and holding a database connection open for that long would
	 * exhaust the pool under any real load. Only the save at the end is
	 * transactional, which is all that needs to be atomic.
	 */
	public AnalysisResponse analyzeReport(UUID reportId) {
		LabReport report = getReportOrThrow(reportId);
		String path = report.getReportPath();

		// The analyzer reads PDFs only. Saying so here beats a 415 from a
		// service the caller did not know was involved.
		if (path == null || !path.toLowerCase().endsWith(".pdf")) {
			throw new ResponseStatusException(HttpStatus.UNSUPPORTED_MEDIA_TYPE,
					"Only PDF reports can be analysed. This report is: " + path);
		}

		StorageService.StoredFile stored = storageService.load(path);

		long startedAt = System.currentTimeMillis();
		Map<String, Object> payload = analyzerClient.analyzeReport(stored.resource());
		int durationMs = (int) (System.currentTimeMillis() - startedAt);

		if (payload == null) {
			throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "The analyzer returned an empty response.");
		}

		// Reuse the existing row when there is one: the unique constraint on
		// report_id means a second insert would fail, and replacing is the
		// intended behaviour anyway.
		Analysis analysis = analysisRepository.findByReportId(reportId).orElseGet(Analysis::new);
		analysis.setReport(report);
		analysis.setPayload(payload);
		analysis.setDurationMs(durationMs);
		analysis.setCreatedAt(Instant.now());
		analysis.setThreadId(asText(payload.get("thread_id")));

		Map<String, Object> summary = asMap(payload.get("summary"));
		analysis.setCriticalCount(asInt(summary.get("critical")));
		analysis.setWarningCount(asInt(summary.get("warning")));
		analysis.setNormalCount(asInt(summary.get("normal")));
		analysis.setUnknownCount(asInt(summary.get("unknown")));
		analysis.setErrorCount(asList(payload.get("errors")).size());
		// Counts come from the analyzer's own summary rather than being trusted
		// from a caller, so the stored severity always matches the payload.
		analysis.setStatus(deriveStatus(analysis));

		return toResponse(analysisRepository.save(analysis));
	}

	/**
	 * Emails a stored report, with its latest analysis in the body.
	 *
	 * Everything the email service needs travels with the request: it has no
	 * database and cannot see the uploads folder.
	 */
	public void emailReport(UUID reportId, String to, String note) {
		LabReport report = getReportOrThrow(reportId);
		StorageService.StoredFile stored = storageService.load(report.getReportPath());

		// getPatient() returns a lazy proxy. Reading its id costs nothing, but
		// reading the name would need an open session, so it is fetched outright.
		String patientName = identityRepository.findById(report.getPatient().getId())
				.map(Identity::getFullName)
				.orElse(null);

		// Null when the report has never been analysed, which is allowed.
		Map<String, Object> payload = analysisRepository.findByReportId(reportId)
				.map(Analysis::getPayload)
				.orElse(null);

		emailClient.sendReport(stored.resource(), to, patientName, payload, note);
	}

	public AnalysisResponse getAnalysis(UUID reportId) {
		getReportOrThrow(reportId);
		return analysisRepository.findByReportId(reportId)
				.map(this::toResponse)
				.orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND,
						"No analysis stored for report " + reportId));
	}

	public ReportResponse getReportById(UUID reportId) {
		LabReport report = getReportOrThrow(reportId);
		return toResponse(report, analysisRepository.findByReportId(reportId).orElse(null));
	}

	public List<ReportResponse> getAllReportsByPatientId(UUID patientId) {
		getPatientOrThrow(patientId);
		List<LabReport> reports = labReportRepository.findByPatientIdOrderByCreatedAtDesc(patientId);
		if (reports.isEmpty()) {
			return List.of();
		}

		// One query for every analysis in the list, rather than one per report.
		Map<UUID, Analysis> byReport = analysisRepository
				.findByReportIdIn(reports.stream().map(LabReport::getId).toList())
				.stream()
				.collect(Collectors.toMap(a -> a.getReport().getId(), Function.identity()));

		return reports.stream().map(report -> toResponse(report, byReport.get(report.getId()))).toList();
	}

	public StorageService.StoredFile loadReportFile(UUID reportId) {
		return storageService.load(getReportOrThrow(reportId).getReportPath());
	}

	public ReportResponse updateReportStatus(UUID reportId, ReportStatus status) {
		LabReport report = getReportOrThrow(reportId);
		report.setStatus(status);

		return toResponse(labReportRepository.save(report), analysisRepository.findByReportId(reportId).orElse(null));
	}

	public void deleteReport(UUID reportId) {
		// The analysis row goes with it: ON DELETE CASCADE on analysis.report_id.
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

	/** Worst finding decides the run: one critical result is never averaged away. */
	private static ReportStatus deriveStatus(Analysis analysis) {
		if (analysis.getCriticalCount() > 0) {
			return ReportStatus.CRITICAL;
		}
		if (analysis.getWarningCount() > 0) {
			return ReportStatus.WARNING;
		}
		return ReportStatus.NORMAL;
	}

	private static int asInt(Object value) {
		return value instanceof Number number ? number.intValue() : 0;
	}

	private static String asText(Object value) {
		return value == null ? null : String.valueOf(value);
	}

	@SuppressWarnings("unchecked")
	private static Map<String, Object> asMap(Object value) {
		return value instanceof Map<?, ?> map ? (Map<String, Object>) map : Map.of();
	}

	private static List<?> asList(Object value) {
		return value instanceof List<?> list ? list : List.of();
	}

	private ReportResponse toResponse(LabReport report, Analysis analysis) {
		return new ReportResponse(report.getId(), report.getPatient().getId(), report.getReportPath(),
				report.getStatus(), report.getCreatedAt(), analysis != null, analysis == null ? null : analysis.getId());
	}

	private AnalysisResponse toResponse(Analysis analysis) {
		return new AnalysisResponse(analysis.getId(), analysis.getReport().getId(), analysis.getThreadId(),
				analysis.getStatus(), analysis.getCriticalCount(), analysis.getWarningCount(),
				analysis.getNormalCount(), analysis.getUnknownCount(), analysis.getErrorCount(),
				analysis.getDurationMs(), analysis.getCreatedAt(), analysis.getPayload());
	}

}
