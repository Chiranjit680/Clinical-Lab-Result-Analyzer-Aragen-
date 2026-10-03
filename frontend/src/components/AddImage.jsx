import { useState } from "react";
import PatientSelect from "./PatientSelect";
import { imageDownloadUrl, uploadImage } from "../patientApi";

// Kept in step with the Modality enum and the CHECK constraint behind it.
const MODALITIES = ["XRAY", "CT", "MRI", "ULTRASOUND", "PET", "MAMMOGRAPHY", "OTHER"];

// The picker's filter is only a hint — every file dialog lets the user switch
// back to "All files" — so the same list is enforced here and again on the
// server, which is the one that actually matters.
const ACCEPTED_EXTENSIONS = [".dcm", ".dicom", ".png", ".jpg", ".jpeg"];

const ACCEPT_ATTRIBUTE = [".dcm", ".dicom", ".png", ".jpg", ".jpeg", "image/png", "image/jpeg"].join(
  ","
);

/**
 * Stores a radiological image against a patient. Filing only — images are not
 * analysed; the lab pipeline reads values, not pixels.
 */
export default function AddImage({ patientsVersion }) {
  const [patientId, setPatientId] = useState("");
  const [file, setFile] = useState(null);
  const [modality, setModality] = useState("XRAY");
  const [bodyPart, setBodyPart] = useState("");
  const [description, setDescription] = useState("");

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
      setError(`"${picked.name}" is not a DICOM, PNG or JPEG image.`);
      return;
    }

    setError("");
    setFile(picked);
  }

  async function handleSave() {
    setSaving(true);
    setError("");
    try {
      setSaved(await uploadImage({ file, patientId, modality, bodyPart, description }));
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  function addAnother() {
    setFile(null);
    setBodyPart("");
    setDescription("");
    setSaved(null);
    setError("");
  }

  const canSave = Boolean(patientId) && Boolean(file) && !saving;

  return (
    <section className="panel">
      <h2 className="panel__title">Add a radiological image</h2>

      <PatientSelect value={patientId} onChange={setPatientId} refreshToken={patientsVersion} />

      <label className="field">
        <span className="field__label">Image file</span>
        <input
          className="field__input"
          type="file"
          accept={ACCEPT_ATTRIBUTE}
          onChange={(event) => chooseFile(event.target.files?.[0] ?? null)}
        />
      </label>
      <p className="hint">
        DICOM, PNG or JPEG, up to 10 MB. Stored for reference — images are not analysed.
      </p>

      {file && (
        <p className="hint">
          Selected: <strong>{file.name}</strong>
        </p>
      )}

      <label className="field">
        <span className="field__label">Modality</span>
        <select
          className="field__input"
          value={modality}
          onChange={(event) => setModality(event.target.value)}
        >
          {MODALITIES.map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </select>
      </label>

      <label className="field">
        <span className="field__label">Body part (optional)</span>
        <input
          className="field__input"
          type="text"
          maxLength={80}
          value={bodyPart}
          onChange={(event) => setBodyPart(event.target.value)}
          placeholder="Chest"
        />
      </label>

      <label className="field">
        <span className="field__label">Description (optional)</span>
        <input
          className="field__input"
          type="text"
          maxLength={500}
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          placeholder="PA view, follow-up after treatment"
        />
      </label>

      {error && (
        <div className="alert" role="alert">
          {error}
        </div>
      )}

      <button type="button" className="btn btn--primary" onClick={handleSave} disabled={!canSave}>
        {saving ? "Saving…" : "Save image"}
      </button>

      {!patientId && <p className="hint">Select a patient to enable saving.</p>}
      {patientId && !file && <p className="hint">Choose an image file to enable saving.</p>}

      {saved && (
        <>
          <p className="saved" role="status">
            Saved <strong>{saved.modality}</strong>
            {saved.bodyPart ? ` (${saved.bodyPart})` : ""} — <code>{saved.id}</code>
            <br />
            <a href={imageDownloadUrl(saved.id)} target="_blank" rel="noreferrer">
              view {saved.imagePath}
            </a>
          </p>

          <button type="button" className="btn btn--ghost" onClick={addAnother}>
            Add another image
          </button>
        </>
      )}
    </section>
  );
}
