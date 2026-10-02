import { useState } from "react";
import labTech from "./assets/labtech.jpeg";
import AddReport from "./components/AddReport";
import ChatPanel from "./components/ChatPanel";
import PatientReports from "./components/PatientReports";
import LabInput from "./components/LabInput";
import LoadingStatus from "./components/LoadingStatus";
import ResultsDisplay from "./components/ResultsDisplay";
import ReportAnalyze from "./components/ReportAnalyze";
import { analyzeLabs, analyzeReportPdf } from "./api";
import "./App.css";

const VIEWS = [
  { id: "analyze", label: "Analyze" },
  { id: "add-report", label: "Add lab report" },
  { id: "patient-reports", label: "Patient reports" },
];

export default function App() {
  const [view, setView] = useState("analyze");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleAnalyze(labs) {
    setLoading(true);
    setError("");
    try {
      setData(await analyzeLabs(labs));
    } catch (err) {
      setError(err.message);
      setData(null);
    } finally {
      setLoading(false);
    }
  }

  /** Document path: the analyzer extracts the values from the PDF itself. */
  async function handleAnalyzeFile(file) {
    if (!file) return;
    setLoading(true);
    setError("");
    try {
      setData(await analyzeReportPdf(file));
    } catch (err) {
      setError(err.message);
      setData(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app">
      {/* Decorative only — fixed to the right edge, behind all content. */}
      <div
        className="app__backdrop"
        style={{ backgroundImage: `url(${labTech})` }}
        aria-hidden="true"
      />

      <header className="app__header">
        <div className="app__brand">
          <span className="app__mark" aria-hidden="true" />
          <div>
            <h1>Lab Results Analyzer</h1>
            <p>Classifies lab results by severity and explains why each one was flagged.</p>
          </div>
        </div>

        <nav className="tabs app__nav" aria-label="Primary">
          {VIEWS.map(({ id, label }) => (
            <button
              key={id}
              type="button"
              className={view === id ? "tab tab--active" : "tab"}
              aria-current={view === id ? "page" : undefined}
              onClick={() => setView(id)}
            >
              {label}
            </button>
          ))}
        </nav>
      </header>

      {/*
        Every view stays mounted and is merely hidden, rather than being
        swapped in and out. Unmounting threw away whatever the view was doing:
        an analysis running on another tab had its result delivered to a dead
        component, and finished results disappeared on the way back.
      */}
      <main className="app__main">
        <div hidden={view !== "analyze"}>
          <ReportAnalyze onAnalyzeFile={handleAnalyzeFile} loading={loading} />

          <LabInput onAnalyze={handleAnalyze} loading={loading} />

          {error && (
            <div className="alert" role="alert">
              {error}
            </div>
          )}

          {loading && <LoadingStatus />}

          {!loading && <ResultsDisplay data={data} />}
          {!loading && data?.thread_id && <ChatPanel threadId={data.thread_id} />}
        </div>

        <div hidden={view !== "add-report"}>
          <AddReport />
        </div>

        <div hidden={view !== "patient-reports"}>
          <PatientReports />
        </div>
      </main>

      <footer className="app__footer">
        Clinical decision support — informational only, not a diagnosis.
      </footer>
    </div>
  );
}
