import { useState } from "react";
import PatientSelect from "./PatientSelect";
import ReportList from "./ReportList";

/**
 * Browsing page: every stored report for one patient, each with its own
 * Analyze button. Read-only - saving new reports happens on the add page.
 */
export default function PatientReports() {
  const [patientId, setPatientId] = useState("");

  return (
    <>
      <section className="panel">
        <h2 className="panel__title">Patient reports</h2>

        <PatientSelect value={patientId} onChange={setPatientId} />

        {!patientId && (
          <p className="hint">Choose a patient to see every lab report stored for them.</p>
        )}
      </section>

      {/* Keyed by patient so switching clears the previous list and any
          analysis still on screen, instead of showing one patient's results
          under another patient's name. */}
      <ReportList key={patientId} patientId={patientId} />
    </>
  );
}
