import { useRef, useState } from "react";
import "./fileUpload.css";

const MAX_MB = 10;

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function FileUpload({ onFileSelect }) {
  const [selectedFile, setSelectedFile] = useState(null);
  const [error, setError] = useState("");
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef(null);

  /** Clears the staged file and tells the parent, so it can't act on stale data. */
  function rejectFile(message) {
    setSelectedFile(null);
    setError(message);
    onFileSelect?.(null);
  }

  function acceptFile(file) {
    // Cancelling the picker fires a change event with no file — not an error.
    if (!file) return;

    // Browsers disagree on the CSV MIME type: Chrome and Firefox usually send
    // "text/csv", Windows with Excel installed sends "application/vnd.ms-excel",
    // and some send nothing at all — so the extension is the reliable check.
    const isCsv =
      ["text/csv", "application/csv", "application/vnd.ms-excel"].includes(file.type) ||
      file.name.toLowerCase().endsWith(".csv");

    if (!isCsv) {
      rejectFile("That file is not a CSV. Please choose a CSV lab report.");
      return;
    }
    if (file.size > MAX_MB * 1024 * 1024) {
      rejectFile(`That file is ${formatSize(file.size)} — the limit is ${MAX_MB} MB.`);
      return;
    }

    setError("");
    setSelectedFile(file);
    // Selecting *is* the upload: the parent gets the file immediately, so there
    // is no second button to press.
    onFileSelect?.(file);
  }

  function handleFileChange(event) {
    acceptFile(event.target.files?.[0]);
  }

  function handleDrop(event) {
    event.preventDefault();
    setDragging(false);
    acceptFile(event.dataTransfer.files?.[0]);
  }

  function clearFile() {
    setSelectedFile(null);
    setError("");
    // Keep the parent in sync, or Analyze stays enabled on a removed file.
    onFileSelect?.(null);
    // Reset the input so picking the same file again still fires onChange.
    if (inputRef.current) inputRef.current.value = "";
  }

  const zoneClass = ["upload__zone", dragging ? "is-dragging" : "", error ? "has-error" : ""]
    .filter(Boolean)
    .join(" ");

  return (
    <section className="upload">
      <div
        className={zoneClass}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
      >
        <input
          ref={inputRef}
          id="lab-report"
          className="upload__input"
          type="file"
          accept="text/csv,.csv"
          onChange={handleFileChange}
        />

        <span className="upload__icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 16V4m0 0L8 8m4-4 4 4" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3" strokeLinecap="round" />
          </svg>
        </span>

        <p className="upload__title">Drop your lab report here</p>
        <p className="upload__hint">CSV, up to {MAX_MB} MB</p>

        <button type="button" className="upload__btn" onClick={() => inputRef.current?.click()}>
          Browse files
        </button>
      </div>

      {error && (
        <p className="upload__error" role="alert">
          {error}
        </p>
      )}

      {selectedFile && (
        <div className="upload__file">
          <span className="upload__badge" aria-hidden="true">
            CSV
          </span>
          <span className="upload__meta">
            <span className="upload__name">{selectedFile.name}</span>
            <span className="upload__size">{formatSize(selectedFile.size)}</span>
          </span>
          <button
            type="button"
            className="upload__remove"
            onClick={clearFile}
            aria-label={`Remove ${selectedFile.name}`}
          >
            ×
          </button>
        </div>
      )}
    </section>
  );
}
