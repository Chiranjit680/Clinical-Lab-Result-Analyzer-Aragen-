const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

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
