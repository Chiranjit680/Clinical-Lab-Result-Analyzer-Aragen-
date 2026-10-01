const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

/** WebSocket URL for follow-up chat on a parked analysis thread. */
export function chatSocketUrl(threadId) {
  return `${API_BASE.replace(/^http/, "ws")}/ws/chat/${threadId}`;
}

export async function analyzeLabs(labs) {
  let response;
  try {
    response = await fetch(`${API_BASE}/analyze_labs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ labs }),
    });
  } catch {
    throw new Error(
      `Cannot reach the analyzer API at ${API_BASE}. Is the backend running (python -m app.main)?`
    );
  }

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Analysis failed (HTTP ${response.status}): ${detail.slice(0, 300)}`);
  }
  return response.json();
}

/**
 * Minimal RFC4180-ish CSV parser — the lab dataset contains quoted fields
 * with embedded commas, so a plain split(",") would corrupt those rows.
 */
export function parseCsv(text) {
  const rows = [];
  let row = [];
  let field = "";
  let inQuotes = false;

  const clean = text.replace(/^﻿/, "").replace(/\r\n/g, "\n").replace(/\r/g, "\n");

  for (let i = 0; i < clean.length; i += 1) {
    const char = clean[i];
    if (inQuotes) {
      if (char === '"') {
        if (clean[i + 1] === '"') {
          field += '"';
          i += 1;
        } else {
          inQuotes = false;
        }
      } else {
        field += char;
      }
    } else if (char === '"') {
      inQuotes = true;
    } else if (char === ",") {
      row.push(field);
      field = "";
    } else if (char === "\n") {
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
    } else {
      field += char;
    }
  }
  if (field !== "" || row.length) {
    row.push(field);
    rows.push(row);
  }

  const nonEmpty = rows.filter((r) => r.some((cell) => cell.trim() !== ""));
  if (!nonEmpty.length) return [];

  const headers = nonEmpty[0].map((h) => h.trim());
  return nonEmpty.slice(1).map((cells) =>
    headers.reduce((obj, header, idx) => {
      obj[header] = (cells[idx] ?? "").trim();
      return obj;
    }, {})
  );
}

/**
 * POST /analyze_report -> AnalyzeLabsResponse
 *
 * Sends a PDF for server-side extraction. Content-Type is left unset so the
 * browser supplies the multipart boundary itself.
 */
export async function analyzeReportPdf(file) {
  const form = new FormData();
  form.append("file", file);

  let response;
  try {
    response = await fetch(`${API_BASE}/analyze_report`, { method: "POST", body: form });
  } catch {
    throw new Error(
      `Cannot reach the analyzer API at ${API_BASE}. Is the backend running (python -m app.main)?`
    );
  }

  if (!response.ok) {
    // FastAPI puts the useful message in `detail`; fall back to raw text.
    const raw = await response.text();
    let detail = raw;
    try {
      detail = JSON.parse(raw).detail ?? raw;
    } catch {
      /* not JSON — keep the raw body */
    }
    throw new Error(`Report analysis failed (HTTP ${response.status}): ${String(detail).slice(0, 300)}`);
  }
  return response.json();
}
