import { useState } from "react";
import { createPatient } from "../patientApi";

// Free-text columns server-side, but a fixed list keeps the data consistent
// and stays inside the length limits the API enforces.
const SEXES = ["Female", "Male", "Other"];
const BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"];

const EMPTY = { fullName: "", dateOfBirth: "", sex: "", bloodGroup: "", pregnant: false };

export default function AddPatient({ onCreated }) {
  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [created, setCreated] = useState(null);

  // Bounds the date picker so a future date of birth is awkward to pick, as
  // well as being rejected below.
  const today = new Date().toISOString().slice(0, 10);

  function set(key, value) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSave() {
    // Mirrors @PastOrPresent on the server: catching it here turns a 400 into
    // an immediate, specific message. ISO dates compare correctly as strings.
    if (form.dateOfBirth > today) {
      setError("Date of birth cannot be in the future.");
      return;
    }

    setSaving(true);
    setError("");
    try {
      const saved = await createPatient({
        fullName: form.fullName.trim(),
        dateOfBirth: form.dateOfBirth,
        sex: form.sex,
        // The column is nullable; an empty string would be stored as one.
        bloodGroup: form.bloodGroup || null,
        pregnant: form.pregnant,
      });
      setCreated(saved);
      // Lets the other tabs refetch, so the new patient is selectable without
      // a page reload.
      onCreated?.(saved);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  function addAnother() {
    setForm(EMPTY);
    setCreated(null);
    setError("");
  }

  const canSave =
    Boolean(form.fullName.trim()) && Boolean(form.dateOfBirth) && Boolean(form.sex) && !saving;

  return (
    <section className="panel">
      <h2 className="panel__title">Add a patient</h2>

      <label className="field">
        <span className="field__label">Full name</span>
        <input
          className="field__input"
          type="text"
          maxLength={120}
          value={form.fullName}
          onChange={(event) => set("fullName", event.target.value)}
          placeholder="Jane A. Doe"
        />
      </label>

      <label className="field">
        <span className="field__label">Date of birth</span>
        <input
          className="field__input"
          type="date"
          max={today}
          value={form.dateOfBirth}
          onChange={(event) => set("dateOfBirth", event.target.value)}
        />
      </label>

      <label className="field">
        <span className="field__label">Sex</span>
        <select
          className="field__input"
          value={form.sex}
          onChange={(event) => set("sex", event.target.value)}
        >
          <option value="">— select —</option>
          {SEXES.map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </select>
      </label>

      <label className="field">
        <span className="field__label">Blood group (optional)</span>
        <select
          className="field__input"
          value={form.bloodGroup}
          onChange={(event) => set("bloodGroup", event.target.value)}
        >
          <option value="">— not recorded —</option>
          {BLOOD_GROUPS.map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </select>
      </label>

      <label className="field">
        <input
          type="checkbox"
          checked={form.pregnant}
          onChange={(event) => set("pregnant", event.target.checked)}
        />{" "}
        <span className="field__label">Pregnant</span>
      </label>
      <p className="hint">
        Pregnancy shifts the reference range for several tests, so it is recorded with the patient
        rather than per report.
      </p>

      {error && (
        <div className="alert" role="alert">
          {error}
        </div>
      )}

      <button type="button" className="btn btn--primary" onClick={handleSave} disabled={!canSave}>
        {saving ? "Saving…" : "Add patient"}
      </button>

      {!canSave && !saving && <p className="hint">Name, date of birth and sex are required.</p>}

      {created && (
        <>
          <p className="saved" role="status">
            Added <strong>{created.fullName}</strong> — <code>{created.id}</code>
            <br />
            They can now be selected on the Add lab report and Patient reports tabs.
          </p>

          <button type="button" className="btn btn--ghost" onClick={addAnother}>
            Add another patient
          </button>
        </>
      )}
    </section>
  );
}
