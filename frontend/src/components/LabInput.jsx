import { useRef, useState } from "react";
import { parseCsv } from "../api";

const EMPTY_ROW = { Test_Name: "", Result: "", Unit: "", Min_Reference: "", Max_Reference: "" };

export default function LabInput({ onAnalyze, loading }) {
  const [mode, setMode] = useState("csv");
  const [rows, setRows] = useState([{ ...EMPTY_ROW }]);
  const [csvRows, setCsvRows] = useState([]);
  const [fileName, setFileName] = useState("");
  const [fileError, setFileError] = useState("");
  const fileInput = useRef(null);

  function handleFile(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    setFileError("");
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const parsed = parseCsv(String(reader.result));
        if (!parsed.length) {
          setFileError("That file has no data rows.");
          setCsvRows([]);
          return;
        }
        setCsvRows(parsed);
        setFileName(file.name);
      } catch {
        setFileError("Could not read that file as CSV.");
        setCsvRows([]);
      }
    };
    reader.onerror = () => setFileError("Could not read that file.");
    reader.readAsText(file);
  }

  function updateRow(index, key, value) {
    setRows((prev) => prev.map((row, i) => (i === index ? { ...row, [key]: value } : row)));
  }

  function submit(event) {
    event.preventDefault();
    if (mode === "csv") {
      if (csvRows.length) onAnalyze(csvRows);
      return;
    }
    const filled = rows.filter((row) => row.Test_Name.trim() && String(row.Result).trim());
    if (filled.length) onAnalyze(filled);
  }

  const canSubmit =
    !loading &&
    (mode === "csv"
      ? csvRows.length > 0
      : rows.some((row) => row.Test_Name.trim() && String(row.Result).trim()));

  return (
    <form className="panel" onSubmit={submit}>
      <div className="tabs" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={mode === "csv"}
          className={mode === "csv" ? "tab tab--active" : "tab"}
          onClick={() => setMode("csv")}
        >
          Upload CSV
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mode === "form"}
          className={mode === "form" ? "tab tab--active" : "tab"}
          onClick={() => setMode("form")}
        >
          Enter manually
        </button>
      </div>

      {mode === "csv" ? (
        <div className="uploader">
          <input
            ref={fileInput}
            id="csv-file"
            type="file"
            accept=".csv,text/csv"
            onChange={handleFile}
            hidden
          />
          <button type="button" className="btn btn--ghost" onClick={() => fileInput.current?.click()}>
            Choose CSV file
          </button>
          {fileName && (
            <p className="uploader__meta">
              <strong>{fileName}</strong> — {csvRows.length} row{csvRows.length === 1 ? "" : "s"} ready
            </p>
          )}
          {fileError && <p className="uploader__error">{fileError}</p>}
          <p className="hint">
            Expected columns: Test_Name, Result, Unit, Min_Reference, Max_Reference (extra columns are ignored).
          </p>
        </div>
      ) : (
        <div className="manual">
          <div className="manual__head">
            <span>Test name</span>
            <span>Result</span>
            <span>Unit</span>
            <span>Ref min</span>
            <span>Ref max</span>
            <span />
          </div>
          {rows.map((row, index) => (
            <div className="manual__row" key={index}>
              <input
                value={row.Test_Name}
                onChange={(e) => updateRow(index, "Test_Name", e.target.value)}
                placeholder="Hemoglobin"
                aria-label="Test name"
              />
              <input
                value={row.Result}
                onChange={(e) => updateRow(index, "Result", e.target.value)}
                placeholder="8.2"
                aria-label="Result"
              />
              <input
                value={row.Unit}
                onChange={(e) => updateRow(index, "Unit", e.target.value)}
                placeholder="g/dL"
                aria-label="Unit"
              />
              <input
                value={row.Min_Reference}
                onChange={(e) => updateRow(index, "Min_Reference", e.target.value)}
                placeholder="12"
                aria-label="Reference minimum"
              />
              <input
                value={row.Max_Reference}
                onChange={(e) => updateRow(index, "Max_Reference", e.target.value)}
                placeholder="15"
                aria-label="Reference maximum"
              />
              <button
                type="button"
                className="btn btn--icon"
                aria-label="Remove row"
                onClick={() => setRows((prev) => prev.filter((_, i) => i !== index))}
                disabled={rows.length === 1}
              >
                ×
              </button>
            </div>
          ))}
          <button
            type="button"
            className="btn btn--ghost"
            onClick={() => setRows((prev) => [...prev, { ...EMPTY_ROW }])}
          >
            + Add another test
          </button>
        </div>
      )}

      <button type="submit" className="btn btn--primary" disabled={!canSubmit}>
        {loading ? "Analyzing…" : "Analyze results"}
      </button>
    </form>
  );
}
