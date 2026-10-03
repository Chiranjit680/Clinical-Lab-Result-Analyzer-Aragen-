/**
 * Client for the Spring Boot patientService (port 8082), which stores patients
 * and lab-report records. Separate from api.js, which talks to the Python
 * analyzer on port 8000 — the two services are independent.
 */
const PATIENT_API_BASE =
  import.meta.env.VITE_PATIENT_API_BASE || "http://127.0.0.1:8082";

async function request(path, options) {
  let response;
  try {
    response = await fetch(`${PATIENT_API_BASE}${path}`, options);
  } catch {
    throw new Error(
      `Cannot reach the patient service at ${PATIENT_API_BASE}. Is it running (./mvnw spring-boot:run)?`
    );
  }

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(
      `${options?.method || "GET"} ${path} failed (HTTP ${response.status}): ${detail.slice(0, 300)}`
    );
  }

  // 204 No Content has an empty body, so response.json() would throw.
  if (response.status === 204) return null;
  return response.json();
}

/** GET /api/identities -> IdentityResponse[] */
export function listPatients() {
  return request("/api/identities");
}

/** POST /api/reports/save -> ReportResponse */
export function saveReport({ patientId, reportPath, status }) {
  return request("/api/reports/save", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ patientId, reportPath, status }),
  });
}

/** GET /api/reports/getall/{patientId} -> ReportResponse[] */
export function listReports(patientId) {
  return request(`/api/reports/getall/${patientId}`);
}

/**
 * POST /api/reports/upload -> ReportResponse
 *
 * Sends the file itself as multipart. Content-Type is deliberately not set:
 * the browser must add it along with the multipart boundary, and setting it
 * by hand produces a body the server cannot parse.
 */
export function uploadReport({ file, patientId, status }) {
  const form = new FormData();
  form.append("file", file);
  form.append("patientId", patientId);
  form.append("status", status);

  return request("/api/reports/upload", { method: "POST", body: form });
}

/** Browser URL for downloading a stored report file. */
export function reportDownloadUrl(reportId) {
  return `${PATIENT_API_BASE}/api/reports/download/${reportId}`;
}

/**
 * Downloads a stored report as a File, ready to post to the analyzer.
 *
 * The name is passed in rather than read from Content-Disposition: that header
 * is not exposed to cross-origin JS unless the server opts in, and the caller
 * already knows the name from the report's reportPath.
 */
export async function fetchReportFile(reportId, filename) {
  let response;
  try {
    response = await fetch(reportDownloadUrl(reportId));
  } catch {
    throw new Error(`Cannot reach the patient service at ${PATIENT_API_BASE}.`);
  }

  if (!response.ok) {
    throw new Error(`Could not download that report (HTTP ${response.status}).`);
  }

  const blob = await response.blob();
  return new File([blob], filename || `report-${reportId}`, { type: blob.type });
}

/**
 * POST /api/reports/{id}/analyze -> AnalysisResponse
 *
 * The patient service fetches its own stored file and calls the analyzer, so
 * the browser never moves the document between services. Runs for a minute or
 * two and replaces any previous analysis for that report.
 */
export function analyzeStoredReport(reportId) {
  return request(`/api/reports/${reportId}/analyze`, { method: "POST" });
}

/** GET /api/reports/{id}/analysis -> AnalysisResponse (404 when none stored). */
export function getReportAnalysis(reportId) {
  return request(`/api/reports/${reportId}/analysis`);
}

/** POST /api/identities -> IdentityResponse */
export function createPatient(patient) {
  return request("/api/identities", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patient),
  });
}

/**
 * POST /api/reports/{id}/email -> { status, to }
 *
 * The patient service loads the file and the stored analysis and hands both to
 * the email service, so nothing travels through the browser.
 */
export function emailReport(reportId, to, note) {
  return request(`/api/reports/${reportId}/email`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ to, note: note || null }),
  });
}

/**
 * POST /api/images/upload -> RadiologyImageResponse
 *
 * Content-Type is left unset so the browser supplies the multipart boundary.
 */
export function uploadImage({ file, patientId, modality, bodyPart, description }) {
  const form = new FormData();
  form.append("file", file);
  form.append("patientId", patientId);
  form.append("modality", modality);
  if (bodyPart) form.append("bodyPart", bodyPart);
  if (description) form.append("description", description);

  return request("/api/images/upload", { method: "POST", body: form });
}

/** GET /api/images/getall/{patientId} -> RadiologyImageResponse[] */
export function listImages(patientId) {
  return request(`/api/images/getall/${patientId}`);
}

/** Browser URL for viewing or downloading a stored image. */
export function imageDownloadUrl(imageId) {
  return `${PATIENT_API_BASE}/api/images/download/${imageId}`;
}

/**
 * Downloads a stored image as a File, ready to post to the VLM service.
 *
 * The name is passed in rather than read from Content-Disposition, which is
 * not exposed to cross-origin JS unless the server opts in.
 */
export async function fetchImageFile(imageId, filename) {
  let response;
  try {
    response = await fetch(imageDownloadUrl(imageId));
  } catch {
    throw new Error(`Cannot reach the patient service at ${PATIENT_API_BASE}.`);
  }

  if (!response.ok) {
    throw new Error(`Could not download that image (HTTP ${response.status}).`);
  }

  const blob = await response.blob();
  return new File([blob], filename || `image-${imageId}`, { type: blob.type });
}

/**
 * PUT /api/images/{id}/analysis -> ImageAnalysisResponse
 *
 * Stores a VLM run against an image, replacing any previous one. The run itself
 * happens in the browser because it takes minutes; this is the save step.
 *
 * The agent service answers in snake_case and the patient service expects
 * camelCase, so the translation lives here — one place, rather than annotations
 * spread through the Java DTO.
 */
export function saveImageAnalysis(imageId, result) {
  return request(`/api/images/${imageId}/analysis`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      answer: result.answer,
      globalSummary: result.global_summary || null,
      question: result.question || null,
      model: result.model || null,
      runId: result.run_id || null,
      seconds: typeof result.seconds === "number" ? result.seconds : null,
      tiles: (result.tiles || []).map((tile) => ({
        tileId: tile.tile_id,
        report: tile.report,
      })),
    }),
  });
}

/** GET /api/images/{id}/analysis -> ImageAnalysisResponse (404 when none). */
export function getImageAnalysis(imageId) {
  return request(`/api/images/${imageId}/analysis`);
}

/** POST /api/images/{id}/email — sends the image with its stored analysis. */
export function emailImage(imageId, to, note) {
  return request(`/api/images/${imageId}/email`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ to, note: note || null }),
  });
}
