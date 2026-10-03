import { useState } from "react";
import PatientSelect from "./PatientSelect";
import { reportDownloadUrl, uploadReport } from "../patientApi";

const STATUSES = ["NORMAL", "WARNING", "CRITICAL"];

// The picker's filter is only a hint — every file dialog lets the user switch
// back to "All files" — so the same list is enforced in the change handler.
const ACCEPTED_EXTENSIONS = [".pdf", ".doc", ".docx"];

const ACCEPT_ATTRIBUTE = [
  ".pdf",
  ".doc",
  ".docx",
  "application/pdf",
  "application/msword",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
].join(",");

/**
 * Stores a lab report against a patient. Filing only — nothing is analysed
 * here; that happens per report on the Patient reports page.
 */
export default function AddReport({ patientsVersion }) {
  const [patientId, setPatientId] = useState("");
  const [file, setFile] = useState(null);
  const [status, setStatus] = useState("NORMAL");

  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(null);

  function chooseFile(picked) {
    // Cancelling the dialog clears the selection without complaining.
    if (!picked) {
      setFile(null);
      return;
    }

    const name = picked.name.toLowerCase();
    if (!ACCEPTED_EXTENSIONS.some((ext) => name.endsWith(ext))) {
      setFile(null);
      setError(`"${picked.name}" is not a PDF or Word document.`);
      return;
    }

    setError("");
    setFile(picked);
  }

  async function handleSave() {
    setSaving(true);
    setError("");
    try {
      setSaved(await uploadReport({ file, patientId, status }));
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  function saveAnother() {
    setFile(null);
    setSaved(null);
    setError("");
  }

  const canSave = Boolean(patientId) && Boolean(file) && !saving;

  return (
    <section className="panel">
      <h2 className="panel__title">Save a lab report</h2>

      <PatientSelect value={patientId} onChange={setPatientId} refreshToken={patientsVersion} />

      <label className="field">
        <span className="field__label">Report file</span>
        <input
          className="field__input"
          type="file"
          accept={ACCEPT_ATTRIBUTE}
          onChange={(event) => chooseFile(event.target.files?.[0] ?? null)}
        />
      </label>
      <p className="hint">
        PDF or Word document, up to 10 MB. The file is stored by the patient service and the saved
        path is generated server-side.
      </p>

      {file && (
        <p className="hint">
          Selected: <strong>{file.name}</strong>
        </p>
      )}

      <label className="field">
        <span className="field__label">Status</span>
        <select
          className="field__input"
          value={status}
          onChange={(event) => setStatus(event.target.value)}
        >
          {STATUSES.map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </select>
      </label>
      <p className="hint">
        A filing label only. Analysing the report later, from the Patient reports page, does not
        change it.
      </p>

      {error && (
        <div className="alert" role="alert">
          {error}
        </div>
      )}

      <button type="button" className="btn btn--primary" onClick={handleSave} disabled={!canSave}>
        {saving ? "Saving…" : "Save report"}
      </button>

      {!patientId && <p className="hint">Select a patient to enable saving.</p>}
      {patientId && !file && <p className="hint">Choose a report file to enable saving.</p>}

      {saved && (
        <>
          <p className="saved" role="status">
            Saved report <code>{saved.id}</code> as <strong>{saved.status}</strong> &mdash;{" "}
            <a href={reportDownloadUrl(saved.id)} target="_blank" rel="noreferrer">
              download {saved.reportPath}
            </a>
            <br />
            Open <strong>Patient reports</strong> to analyse it.
          </p>

          <button type="button" className="btn btn--ghost" onClick={saveAnother}>
            Save another report
          </button>
        </>
      )}
    </section>
  );
}
