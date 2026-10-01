import { useState } from "react";
import labTech from "./assets/labtech.jpeg";
import AddReport from "./components/AddReport";
import ChatPanel from "./components/ChatPanel";
import LabInput from "./components/LabInput";
import LoadingStatus from "./components/LoadingStatus";
import ResultsDisplay from "./components/ResultsDisplay";
import { analyzeLabs } from "./api";
import "./App.css";

const VIEWS = [
  { id: "analyze", label: "Analyze" },
  { id: "reports", label: "Add lab report" },
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

      <main className="app__main">
        {view === "analyze" ? (
          <>
            <LabInput onAnalyze={handleAnalyze} loading={loading} />

            {error && (
              <div className="alert" role="alert">
                {error}
              </div>
            )}

            {loading && <LoadingStatus />}

            {!loading && <ResultsDisplay data={data} />}
            {!loading && data?.thread_id && <ChatPanel threadId={data.thread_id} />}
          </>
        ) : (
          <AddReport />
        )}
      </main>

      <footer className="app__footer">
        Clinical decision support — informational only, not a diagnosis.
      </footer>
    </div>
  );
}
