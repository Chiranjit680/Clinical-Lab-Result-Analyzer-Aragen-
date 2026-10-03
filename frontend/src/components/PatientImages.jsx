import { useEffect, useState } from "react";
import PatientSelect from "./PatientSelect";
import {
  emailImage,
  fetchImageFile,
  getImageAnalysis,
  imageDownloadUrl,
  listImages,
  saveImageAnalysis,
} from "../patientApi";
import { analyzeImage } from "../vlmApi";

function fileNameOf(imagePath) {
  return String(imagePath || "").split("/").pop() || "";
}

function formatWhen(createdAt) {
  if (!createdAt) return "";
  const when = new Date(createdAt);
  return Number.isNaN(when.getTime()) ? "" : when.toLocaleString();
}

// Pillow cannot open DICOM without a plugin, so the service rejects it with a
// 415. Disabling the button here says so before a minutes-long round trip.
function isAnalysable(name) {
  const lower = name.toLowerCase();
  return lower.endsWith(".png") || lower.endsWith(".jpg") || lower.endsWith(".jpeg");
}

/** Browse a patient's radiological images, analyse one, save it, email it. */
export default function PatientImages({ patientsVersion }) {
  const [patientId, setPatientId] = useState("");
  const [images, setImages] = useState([]);
  const [listError, setListError] = useState("");

  const [busyId, setBusyId] = useState(null);
  const [error, setError] = useState("");

  // The image the lower panel is about, and the analysis being shown for it.
  // `stored` is what drives the Save button: an analysis that came out of the
  // database, or has just been written to it, does not need saving again.
  const [active, setActive] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [stored, setStored] = useState(false);
  const [savedAt, setSavedAt] = useState("");
  const [saving, setSaving] = useState(false);

  const [emailTo, setEmailTo] = useState("");
  const [emailNote, setEmailNote] = useState("");
  const [emailBusy, setEmailBusy] = useState(false);
  const [emailStatus, setEmailStatus] = useState("");

  useEffect(() => {
    if (!patientId) return undefined;

    let cancelled = false;
    listImages(patientId)
      .then((rows) => {
        if (!cancelled) setImages(rows || []);
      })
      .catch((err) => {
        if (!cancelled) setListError(err.message);
      });

    return () => {
      cancelled = true;
    };
  }, [patientId]);

  function clearPanel() {
    setActive(null);
    setAnalysis(null);
    setStored(false);
    setSavedAt("");
    setError("");
    setEmailStatus("");
  }

  function choosePatient(id) {
    // A previous patient's images and analysis must not linger under a new name.
    setPatientId(id);
    setImages([]);
    setListError("");
    clearPanel();
  }

  /** Flips analysisAvailable locally, so Previous enables without a refetch. */
  function markAnalysed(imageId, analysisId) {
    setImages((rows) =>
      rows.map((row) =>
        row.id === imageId ? { ...row, analysisAvailable: true, analysisId } : row
      )
    );
  }

  async function handleAnalyze(image) {
    const name = fileNameOf(image.imagePath);
    setBusyId(image.id);
    clearPanel();

    try {
      // The file is fetched here and posted on: the VLM service holds no
      // database and cannot see the uploads folder.
      const file = await fetchImageFile(image.id, name);
      setAnalysis(await analyzeImage(file));
      setActive({ imageId: image.id, name });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyId(null);
    }
  }

  async function handleShowPrevious(image) {
    const name = fileNameOf(image.imagePath);
    setBusyId(image.id);
    clearPanel();

    try {
      const row = await getImageAnalysis(image.id);
      // The payload is the agent service's own response shape, so it renders
      // with exactly the same markup as a live run.
      setAnalysis(row.payload || { answer: row.answer });
      setStored(true);
      setSavedAt(row.createdAt);
      setActive({ imageId: image.id, name });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyId(null);
    }
  }

  async function handleSave() {
    if (!active || !analysis) return;
    setSaving(true);
    setError("");

    try {
      const row = await saveImageAnalysis(active.imageId, analysis);
      setStored(true);
      setSavedAt(row.createdAt);
      markAnalysed(active.imageId, row.id);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  function handleEmailTarget(image) {
    const name = fileNameOf(image.imagePath);
    clearPanel();
    setActive({ imageId: image.id, name });
    setStored(Boolean(image.analysisAvailable));
  }

  async function handleSend(event) {
    event.preventDefault();
    if (!active) return;

    setEmailBusy(true);
    setEmailStatus("");
    setError("");

    try {
      await emailImage(active.imageId, emailTo.trim(), emailNote.trim());
      setEmailStatus(`Sent to ${emailTo.trim()}.`);
      setEmailNote("");
    } catch (err) {
      setError(err.message);
    } finally {
      setEmailBusy(false);
    }
  }

  const activeRow = active ? images.find((row) => row.id === active.imageId) : null;
  // What the server will attach: the stored analysis, which is not necessarily
  // the one on screen if this one has not been saved.
  const willAttachAnalysis = Boolean(activeRow?.analysisAvailable);

  if (!patientId && !images.length) {
    return (
      <section className="panel">
        <h2 className="panel__title">Patient images</h2>
        <PatientSelect value={patientId} onChange={choosePatient} refreshToken={patientsVersion} />
        <p className="hint">Choose a patient to see their stored radiological images.</p>
      </section>
    );
  }

  return (
    <>
      <section className="panel">
        <h2 className="panel__title">Patient images</h2>
        <PatientSelect value={patientId} onChange={choosePatient} refreshToken={patientsVersion} />

        {listError && (
          <div className="alert" role="alert">
            {listError}
          </div>
        )}

        {!listError && images.length === 0 && (
          <p className="hint">No images stored for this patient yet.</p>
        )}

        {images.length > 0 && (
          <p className="hint">
            Analysis runs a whole-image agent plus a grid of region agents, each allowed a couple
            of tool steps — many model calls, so expect it to take a while. PNG and JPEG only;
            DICOM cannot be read. A finished analysis is kept only once you save it, and saving
            replaces the previous one for that image.
          </p>
        )}

        {images.length > 0 && (
          <ul className="reports">
            {images.map((image) => {
              const name = fileNameOf(image.imagePath);
              const analysable = isAnalysable(name);
              const busy = busyId !== null || saving;
              return (
                <li className="reports__item" key={image.id}>
                  <div className="reports__meta">
                    <span className="reports__name">{name}</span>
                    <span className="reports__when">
                      {image.modality}
                      {image.bodyPart ? ` · ${image.bodyPart}` : ""} · {formatWhen(image.createdAt)}
                      {image.analysisAvailable ? " · analysed" : ""}
                    </span>
                  </div>

                  <a href={imageDownloadUrl(image.id)} target="_blank" rel="noreferrer">
                    View
                  </a>

                  <button
                    type="button"
                    className="btn btn--ghost"
                    onClick={() => handleAnalyze(image)}
                    disabled={busy || !analysable}
                    title={
                      analysable
                        ? "Run the VLM agents over this image"
                        : "Only PNG and JPEG can be analysed"
                    }
                  >
                    {busyId === image.id ? "Analyzing…" : "Analyze"}
                  </button>

                  <button
                    type="button"
                    className="btn btn--ghost"
                    onClick={() => handleShowPrevious(image)}
                    disabled={busy || !image.analysisAvailable}
                    title={
                      image.analysisAvailable
                        ? "Show the analysis stored for this image"
                        : "No analysis has been saved for this image yet"
                    }
                  >
                    See previous analysis
                  </button>

                  <button
                    type="button"
                    className="btn btn--ghost"
                    onClick={() => handleEmailTarget(image)}
                    disabled={busy}
                    title="Send this image, and its saved analysis, by email"
                  >
                    Email
                  </button>
                </li>
              );
            })}
          </ul>
        )}

        {error && (
          <div className="alert" role="alert">
            {error}
          </div>
        )}

        {busyId !== null && (
          <p className="hint" role="status">
            Running the agents — this can take several minutes.
          </p>
        )}
      </section>

      {!busyId && active && analysis && (
        <section className="panel">
          <h2 className="panel__title">Image analysis</h2>
          <p className="hint">
            {active.name}
            {analysis.model ? ` · ${analysis.model}` : ""}
            {typeof analysis.seconds === "number" ? ` · ${analysis.seconds}s` : ""}
            {analysis.tiles?.length ? ` · ${analysis.tiles.length} region agents` : ""}
            {stored && savedAt ? ` · saved ${formatWhen(savedAt)}` : ""}
          </p>

          {analysis.question && <p className="hint">Question asked: {analysis.question}</p>}

          <h3 className="section__title">Findings</h3>
          <p className="vlm__answer">{analysis.answer}</p>

          {analysis.global_summary && (
            <>
              <h3 className="section__title">Whole-image view</h3>
              <p className="vlm__answer">{analysis.global_summary}</p>
            </>
          )}

          {analysis.tiles?.length > 0 && (
            <details className="card__sources">
              <summary>Per-region reports ({analysis.tiles.length})</summary>
              {analysis.tiles.map((tile) => (
                <div className="card__block" key={tile.tile_id}>
                  <h4>{tile.tile_id}</h4>
                  <p>{tile.report}</p>
                </div>
              ))}
            </details>
          )}

          <div className="form__row">
            <button type="button" className="btn" onClick={handleSave} disabled={saving || stored}>
              {saving ? "Saving…" : stored ? "Saved" : "Save analysis"}
            </button>
            {!stored && (
              <span className="hint">
                Not stored yet. Saving replaces any analysis already held for this image.
              </span>
            )}
          </div>
        </section>
      )}

      {!busyId && active && (
        <section className="panel">
          <h2 className="panel__title">Send by email</h2>
          <p className="hint">
            Sends {active.name} as an attachment.{" "}
            {willAttachAnalysis
              ? "Its saved analysis is included in the message body."
              : "No analysis is saved for this image, so the message will say so — save one first to include it."}
          </p>

          <form onSubmit={handleSend}>
            <label className="field">
              <span className="field__label">Recipient email</span>
              <input
                className="field__input"
                type="email"
                required
                value={emailTo}
                onChange={(event) => setEmailTo(event.target.value)}
                placeholder="doctor@example.com"
              />
            </label>

            <label className="field">
              <span className="field__label">Note (optional)</span>
              <textarea
                className="field__input"
                rows={3}
                value={emailNote}
                onChange={(event) => setEmailNote(event.target.value)}
                placeholder="A line of context for the recipient."
              />
            </label>

            <button type="submit" className="btn" disabled={emailBusy || !emailTo.trim()}>
              {emailBusy ? "Sending…" : "Send"}
            </button>
          </form>

          {emailStatus && <p className="hint">{emailStatus}</p>}
        </section>
      )}
    </>
  );
}
