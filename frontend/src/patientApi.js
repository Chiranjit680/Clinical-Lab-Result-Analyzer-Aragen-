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
