import { useEffect, useState } from "react";
import LabInput from "./LabInput";
import LoadingStatus from "./LoadingStatus";
import ReportList from "./ReportList";
import ResultsDisplay from "./ResultsDisplay";
import { analyzeLabs } from "../api";
import { listPatients, reportDownloadUrl, uploadReport } from "../patientApi";

/**
 * The worst finding decides the record's status, so a single critical result
 * is never buried by a majority of normal ones.
 * Mirrors the ReportStatus enum in patientService (NORMAL | WARNING | CRITICAL).
 */
function deriveStatus(summary) {
  if ((summary?.critical ?? 0) > 0) return "CRITICAL";
  if ((summary?.warning ?? 0) > 0) return "WARNING";
  return "NORMAL";
}

function patientLabel(patient) {
  const dob = patient.dateOfBirth ? ` · b. ${patient.dateOfBirth}` : "";
  return `${patient.fullName}${dob}`;
}

export default function AddReport() {
  const [patients, setPatients] = useState([]);
  const [patientsError, setPatientsError] = useState("");
  const [patientId, setPatientId] = useState("");
  const [file, setFile] = useState(null);

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(null);

  useEffect(() => {
    let cancelled = false;
    listPatients()
      .then((rows) => {
        if (!cancelled) setPatients(rows || []);
      })
      .catch((err) => {
        if (!cancelled) setPatientsError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleAnalyze(labs) {
    setLoading(true);
    setError("");
    setSaved(null);
    try {
      setData(await analyzeLabs(labs));
    } catch (err) {
      setError(err.message);
      setData(null);
    } finally {
      setLoading(false);
    }
  }

  async function handleSave() {
    setSaving(true);
    setError("");
    try {
      setSaved(
        await uploadReport({
          file,
          patientId,
          status: deriveStatus(data?.summary),
        })
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  const status = data ? deriveStatus(data.summary) : null;
  const canSave = Boolean(patientId) && Boolean(file) && Boolean(data) && !saving;

  return (
    <>
      <section className="panel">
        <h2 className="panel__title">1 · Choose a patient</h2>

        {patientsError ? (
          <div className="alert" role="alert">
            {patientsError}
          </div>
        ) : (
          <label className="field">
            <span className="field__label">Patient</span>
            <select
              className="field__input"
              value={patientId}
              onChange={(event) => setPatientId(event.target.value)}
            >
              <option value="">— select a patient —</option>
              {patients.map((patient) => (
                <option key={patient.id} value={patient.id}>
                  {patientLabel(patient)}
                </option>
              ))}
            </select>
          </label>
        )}

        {!patientsError && patients.length === 0 && (
          <p className="hint">
            No patients found. Create one first via POST /api/identities on the patient service.
          </p>
        )}
      </section>

      {/* key remounts on patient change, clearing reports and any analysis shown */}
      <ReportList key={patientId} patientId={patientId} />

      <section className="panel">
        <h2 className="panel__title">2 · Enter the lab values</h2>
        <LabInput onAnalyze={handleAnalyze} loading={loading} />
      </section>

      {error && (
        <div className="alert" role="alert">
          {error}
        </div>
      )}

      {loading && <LoadingStatus />}

      {!loading && data && (
        <>
          <ResultsDisplay data={data} />

          <section className="panel">
            <h2 className="panel__title">3 · Save the report record</h2>

            <label className="field">
              <span className="field__label">Report file</span>
              <input
                className="field__input"
                type="file"
                onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              />
            </label>
            <p className="hint">
              Uploaded and stored by the patient service, up to 10 MB. The saved path is generated
              server-side.
            </p>

            <p className="field__derived">
              Status derived from the analysis: <strong>{status}</strong>
            </p>

            <button
              type="button"
              className="btn btn--primary"
              onClick={handleSave}
              disabled={!canSave}
            >
              {saving ? "Saving…" : "Save report"}
            </button>

            {!patientId && <p className="hint">Select a patient above to enable saving.</p>}

            {saved && (
              <p className="saved" role="status">
                Saved report <code>{saved.id}</code> as <strong>{saved.status}</strong> &mdash;{" "}
                <a href={reportDownloadUrl(saved.id)} target="_blank" rel="noreferrer">
                  download {saved.reportPath}
                </a>
              </p>
            )}
          </section>
        </>
      )}
    </>
  );
}
