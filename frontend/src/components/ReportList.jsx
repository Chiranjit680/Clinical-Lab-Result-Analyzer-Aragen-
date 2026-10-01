import { useEffect, useState } from "react";
import LoadingStatus from "./LoadingStatus";
import ResultsDisplay from "./ResultsDisplay";
import SeverityBadge from "./SeverityBadge";
import { analyzeLabs, analyzeReportPdf, parseCsv } from "../api";
import { fetchReportFile, listReports, reportDownloadUrl } from "../patientApi";

function fileNameOf(reportPath) {
  return String(reportPath || "").split("/").pop() || "";
}

function formatWhen(createdAt) {
  if (!createdAt) return "";
  const when = new Date(createdAt);
  return Number.isNaN(when.getTime()) ? "" : when.toLocaleString();
}

export default function ReportList({ patientId }) {
  const [reports, setReports] = useState([]);
  const [listError, setListError] = useState("");
  const [busyId, setBusyId] = useState(null);
  const [error, setError] = useState("");
  const [data, setData] = useState(null);

  useEffect(() => {
    if (!patientId) return undefined;

    // No state reset needed here: AddReport keys this component by patientId,
    // so a patient change remounts it with fresh state.
    let cancelled = false;
    listReports(patientId)
      .then((rows) => {
        if (!cancelled) setReports(rows || []);
      })
      .catch((err) => {
        if (!cancelled) setListError(err.message);
      });

    // A slow response for a previously selected patient must not overwrite the
    // list for the one now selected.
    return () => {
      cancelled = true;
    };
  }, [patientId]);

  async function handleAnalyze(report) {
    const name = fileNameOf(report.reportPath);
    setBusyId(report.id);
    setError("");
    setData(null);

    try {
      const file = await fetchReportFile(report.id, name);
      const lower = name.toLowerCase();

      if (lower.endsWith(".pdf")) {
        // PDFs are extracted server-side by the LLM.
        setData(await analyzeReportPdf(file));
      } else if (lower.endsWith(".csv")) {
        // CSVs already have structure, so parsing here skips an LLM round trip.
        const rows = parseCsv(await file.text());
        if (!rows.length) throw new Error("That CSV has no data rows.");
        setData(await analyzeLabs(rows));
      } else {
        throw new Error(`Cannot analyze "${name}" — only PDF and CSV reports are supported.`);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyId(null);
    }
  }

  if (!patientId) return null;

  return (
    <section className="panel">
      <h2 className="panel__title">Stored reports</h2>

      {listError && (
        <div className="alert" role="alert">
          {listError}
        </div>
      )}

      {!listError && reports.length === 0 && (
        <p className="hint">No reports stored for this patient yet.</p>
      )}

      {reports.length > 0 && (
        <ul className="reports">
          {reports.map((report) => (
            <li className="reports__item" key={report.id}>
              <div className="reports__meta">
                <span className="reports__name">{fileNameOf(report.reportPath)}</span>
                <span className="reports__when">{formatWhen(report.createdAt)}</span>
              </div>

              <SeverityBadge status={report.status} />

              <a href={reportDownloadUrl(report.id)} target="_blank" rel="noreferrer">
                Download
              </a>

              <button
                type="button"
                className="btn btn--ghost"
                onClick={() => handleAnalyze(report)}
                disabled={busyId !== null}
              >
                {busyId === report.id ? "Analyzing…" : "Analyze"}
              </button>
            </li>
          ))}
        </ul>
      )}

      {error && (
        <div className="alert" role="alert">
          {error}
        </div>
      )}

      {busyId !== null && <LoadingStatus />}

      {busyId === null && data && <ResultsDisplay data={data} />}
    </section>
  );
}
