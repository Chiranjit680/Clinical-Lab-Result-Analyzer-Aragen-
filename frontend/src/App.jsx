import { useState } from "react";
import labTech from "./assets/labtech.jpeg";
import BackgroundDecor from "./components/BackgroundDecor";
import AddImage from "./components/AddImage";
import AddPatient from "./components/AddPatient";
import AddReport from "./components/AddReport";
import ChatPanel from "./components/ChatPanel";
import PatientImages from "./components/PatientImages";
import PatientReports from "./components/PatientReports";
import SendReport from "./components/SendReport";
import LabInput from "./components/LabInput";
import LoadingStatus from "./components/LoadingStatus";
import ResultsDisplay from "./components/ResultsDisplay";
import ReportAnalyze from "./components/ReportAnalyze";
import { analyzeLabs, analyzeReportPdf } from "./api";
import "./App.css";

// Ordered the way the work flows: a patient exists before a report is filed
// against them, and reports exist before there is anything to browse.
const VIEWS = [
  { id: "analyze", label: "Analyze" },
  { id: "add-patient", label: "Add patient" },
  { id: "add-report", label: "Add lab report" },
  { id: "add-image", label: "Add image" },
  { id: "patient-reports", label: "Patient reports" },
  { id: "patient-images", label: "Patient images" },
  { id: "send-report", label: "Send report" },
];

export default function App() {
  const [view, setView] = useState("analyze");
  // Bumped whenever a patient is added. Every view stays mounted, so without
  // this the patient dropdowns would keep showing the list they fetched at
  // startup and a new patient would be unselectable until a page reload.
  const [patientsVersion, setPatientsVersion] = useState(0);
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

      <BackgroundDecor />

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

        <div hidden={view !== "add-patient"}>
          <AddPatient onCreated={() => setPatientsVersion((version) => version + 1)} />
        </div>

        <div hidden={view !== "add-report"}>
          <AddReport patientsVersion={patientsVersion} />
        </div>

        <div hidden={view !== "add-image"}>
          <AddImage patientsVersion={patientsVersion} />
        </div>

        <div hidden={view !== "patient-reports"}>
          <PatientReports patientsVersion={patientsVersion} />
        </div>

        <div hidden={view !== "patient-images"}>
          <PatientImages patientsVersion={patientsVersion} />
        </div>

        <div hidden={view !== "send-report"}>
          <SendReport patientsVersion={patientsVersion} />
        </div>
      </main>

      <footer className="app__footer">
        Clinical decision support — informational only, not a diagnosis.
      </footer>
    </div>
  );
}
