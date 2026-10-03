import { useEffect, useState } from "react";
import PatientSelect from "./PatientSelect";
import SeverityBadge from "./SeverityBadge";
import { emailReport, listReports } from "../patientApi";

// Deliberately loose: the server validates with @Email, and this only exists
// to disable the button before an obviously incomplete address is submitted.
const LOOKS_LIKE_EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function fileNameOf(reportPath) {
  return String(reportPath || "").split("/").pop() || "";
}

function formatWhen(createdAt) {
  if (!createdAt) return "";
  const when = new Date(createdAt);
  return Number.isNaN(when.getTime()) ? "" : when.toLocaleString();
}

/**
 * Browse a patient's reports and email one, with its latest analysis included
 * in the message body.
 */
export default function SendReport({ patientsVersion }) {
  const [patientId, setPatientId] = useState("");
  const [reports, setReports] = useState([]);
  const [listError, setListError] = useState("");

  const [selectedId, setSelectedId] = useState("");
  const [to, setTo] = useState("");
  const [note, setNote] = useState("");

  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [sent, setSent] = useState(null);

  useEffect(() => {
    if (!patientId) return undefined;

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

  function choosePatient(id) {
    // The previous patient's reports and selection must not linger under a new
    // name, and a sent confirmation refers to a report no longer on screen.
    setPatientId(id);
    setReports([]);
    setSelectedId("");
    setListError("");
    setSent(null);
    setError("");
  }

  async function handleSend() {
    setSending(true);
    setError("");
    setSent(null);
    try {
      const result = await emailReport(selectedId, to.trim(), note.trim());
      setSent(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setSending(false);
    }
  }

  const selected = reports.find((report) => report.id === selectedId);
  const canSend = Boolean(selectedId) && LOOKS_LIKE_EMAIL.test(to.trim()) && !sending;

  return (
    <>
      <section className="panel">
        <h2 className="panel__title">1 · Choose a patient</h2>
        <PatientSelect value={patientId} onChange={choosePatient} refreshToken={patientsVersion} />
      </section>

      {patientId && (
        <section className="panel">
          <h2 className="panel__title">2 · Choose a report</h2>

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
                  <input
                    type="radio"
                    name="report"
                    checked={selectedId === report.id}
                    onChange={() => setSelectedId(report.id)}
                    aria-label={`Select ${fileNameOf(report.reportPath)}`}
                  />

                  <div className="reports__meta">
                    <span className="reports__name">{fileNameOf(report.reportPath)}</span>
                    <span className="reports__when">
                      {formatWhen(report.createdAt)}
                      {report.analysisAvailable ? " · analysis included" : " · not analysed"}
                    </span>
                  </div>

                  <SeverityBadge status={report.status} />
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {selectedId && (
        <section className="panel">
          <h2 className="panel__title">3 · Send it</h2>

          <label className="field">
            <span className="field__label">Recipient email</span>
            <input
              className="field__input"
              type="email"
              value={to}
              onChange={(event) => setTo(event.target.value)}
              placeholder="doctor@clinic.com"
            />
          </label>

          <label className="field">
            <span className="field__label">Note (optional)</span>
            <input
              className="field__input"
              type="text"
              maxLength={2000}
              value={note}
              onChange={(event) => setNote(event.target.value)}
              placeholder="Please review the flagged potassium result."
            />
          </label>

          <p className="hint">
            {selected?.analysisAvailable
              ? "The report is attached and its latest analysis is written into the message body."
              : "The report is attached. It has not been analysed, so the message will say so."}
          </p>

          {error && (
            <div className="alert" role="alert">
              {error}
            </div>
          )}

          <button
            type="button"
            className="btn btn--primary"
            onClick={handleSend}
            disabled={!canSend}
          >
            {sending ? "Sending…" : "Send report"}
          </button>

          {!LOOKS_LIKE_EMAIL.test(to.trim()) && (
            <p className="hint">Enter a recipient address to enable sending.</p>
          )}

          {sent && (
            <p className="saved" role="status">
              Sent to <strong>{sent.to}</strong>.
            </p>
          )}
        </section>
      )}
    </>
  );
}
