import { useEffect, useState } from "react";
import LoadingStatus from "./LoadingStatus";
import ResultsDisplay from "./ResultsDisplay";
import SeverityBadge from "./SeverityBadge";
import {
  analyzeStoredReport,
  getReportAnalysis,
  listReports,
  reportDownloadUrl,
} from "../patientApi";

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

  // Separate ids rather than one flag: running an analysis and opening a
  // stored one are very different waits, and the buttons say so.
  const [analyzingId, setAnalyzingId] = useState(null);
  const [openingId, setOpeningId] = useState(null);

  const [error, setError] = useState("");
  const [analysis, setAnalysis] = useState(null);

  useEffect(() => {
    if (!patientId) return undefined;

    // No state reset needed: the parent keys this component by patientId, so a
    // patient change remounts it with fresh state.
    let cancelled = false;
    listReports(patientId)
      .then((rows) => {
        if (!cancelled) setReports(rows || []);
      })
      .catch((err) => {
        if (!cancelled) setListError(err.message);
      });

    return () => {
      cancelled = true;
    };
  }, [patientId]);

  /** Re-reads the list after an analysis, so analysisAvailable flips true. */
  async function refresh() {
    try {
      setReports((await listReports(patientId)) || []);
    } catch (err) {
      setListError(err.message);
    }
  }

  async function handleAnalyze(report) {
    setAnalyzingId(report.id);
    setError("");
    setAnalysis(null);

    try {
      const saved = await analyzeStoredReport(report.id);
      setAnalysis(saved);
      // Reload so analysisAvailable flips true and "See previous analysis"
      // becomes usable without a manual refresh.
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setAnalyzingId(null);
    }
  }

  async function handleShowPrevious(report) {
    setOpeningId(report.id);
    setError("");
    setAnalysis(null);

    try {
      setAnalysis(await getReportAnalysis(report.id));
    } catch (err) {
      setError(err.message);
    } finally {
      setOpeningId(null);
    }
  }

  if (!patientId) return null;

  const busy = analyzingId !== null || openingId !== null;

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
        <p className="hint">
          Analysing a full panel takes a minute or two — every abnormal result is researched before
          it is explained. The result is saved against the report, replacing any earlier one, and
          can be reopened later without re-running it.
        </p>
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
                disabled={busy}
              >
                {analyzingId === report.id ? "Analyzing…" : "Analyze"}
              </button>

              <button
                type="button"
                className="btn btn--ghost"
                onClick={() => handleShowPrevious(report)}
                disabled={busy || !report.analysisAvailable}
                title={
                  report.analysisAvailable
                    ? "Open the saved analysis"
                    : "This report has not been analysed yet"
                }
              >
                {openingId === report.id ? "Opening…" : "See previous analysis"}
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

      {analyzingId !== null && <LoadingStatus />}

      {!busy && analysis && (
        <>
          <p className="hint">
            Analysis from {formatWhen(analysis.createdAt)}
            {analysis.durationMs ? ` · took ${Math.round(analysis.durationMs / 1000)}s` : ""}
          </p>
          <ResultsDisplay data={analysis.payload} />
        </>
      )}
    </section>
  );
}
