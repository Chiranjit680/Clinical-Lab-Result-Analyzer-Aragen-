import { useRef, useState } from "react";

// The picker's filter is only a hint — every file dialog lets the user switch
// back to "All files" — so the same list is enforced before anything is sent.
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
 * Upload a report document and analyse it directly, without filing it against
 * a patient first. `onAnalyzeFile` receives the chosen File.
 */
export default function ReportAnalyze({ onAnalyzeFile, loading }) {
  const [file, setFile] = useState(null);
  const [fileError, setFileError] = useState("");
  const fileInput = useRef(null);

  function choose(picked) {
    if (!picked) {
      setFile(null);
      return;
    }

    const name = picked.name.toLowerCase();
    if (!ACCEPTED_EXTENSIONS.some((ext) => name.endsWith(ext))) {
      setFile(null);
      setFileError(`"${picked.name}" is not a PDF or Word document.`);
      return;
    }

    // Word documents are accepted by the picker but the analyzer cannot read
    // values out of them, so say so here rather than after a failed upload.
    if (!name.endsWith(".pdf")) {
      setFile(null);
      setFileError(`Only PDFs can be analysed. "${picked.name}" cannot be read for lab values.`);
      return;
    }

    setFileError("");
    setFile(picked);
  }

  return (
    <div className="panel">
      <h2 className="panel__title">Analyse a report</h2>

      <div className="uploader">
        <input
          ref={fileInput}
          id="report-file"
          type="file"
          accept={ACCEPT_ATTRIBUTE}
          onChange={(event) => choose(event.target.files?.[0] ?? null)}
          hidden
        />
        <button
          type="button"
          className="btn btn--ghost"
          onClick={() => fileInput.current?.click()}
          disabled={loading}
        >
          Choose report file
        </button>

        {file && (
          <p className="uploader__meta">
            <strong>{file.name}</strong> ready
          </p>
        )}
        {fileError && <p className="uploader__error">{fileError}</p>}

        <p className="hint">
          PDF or Word document. Values are extracted from PDFs by the analyzer; scanned PDFs will
          not work, as there is no OCR. A full panel takes a minute or two.
        </p>
      </div>

      <button
        type="button"
        className="btn btn--primary"
        onClick={() => onAnalyzeFile(file)}
        disabled={!file || loading}
      >
        {loading ? "Analyzing…" : "Analyze report"}
      </button>
    </div>
  );
}
