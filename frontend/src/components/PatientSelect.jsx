import { useEffect, useState } from "react";
import { listPatients } from "../patientApi";

function patientLabel(patient) {
  const dob = patient.dateOfBirth ? ` · b. ${patient.dateOfBirth}` : "";
  return `${patient.fullName}${dob}`;
}

/** Patient dropdown, shared by the add-report and patient-reports pages. */
export default function PatientSelect({ value, onChange, label = "Patient" }) {
  const [patients, setPatients] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    listPatients()
      .then((rows) => {
        if (!cancelled) setPatients(rows || []);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) {
    return (
      <div className="alert" role="alert">
        {error}
      </div>
    );
  }

  return (
    <>
      <label className="field">
        <span className="field__label">{label}</span>
        <select
          className="field__input"
          value={value}
          onChange={(event) => onChange(event.target.value)}
        >
          <option value="">— select a patient —</option>
          {patients.map((patient) => (
            <option key={patient.id} value={patient.id}>
              {patientLabel(patient)}
            </option>
          ))}
        </select>
      </label>

      {patients.length === 0 && (
        <p className="hint">
          No patients found. Create one first via POST /api/identities on the patient service.
        </p>
      )}
    </>
  );
}
