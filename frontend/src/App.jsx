import { useState } from "react";
import LabInput from "./components/LabInput";
import LoadingStatus from "./components/LoadingStatus";
import ResultsDisplay from "./components/ResultsDisplay";
import { analyzeLabs } from "./api";
import "./App.css";

export default function App() {
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
      <header className="app__header">
        <div className="app__brand">
          <span className="app__mark" aria-hidden="true" />
          <div>
            <h1>Lab Results Analyzer</h1>
            <p>Classifies lab results by severity and explains why each one was flagged.</p>
          </div>
        </div>
      </header>

      <main className="app__main">
        <LabInput onAnalyze={handleAnalyze} loading={loading} />

        {error && (
          <div className="alert" role="alert">
            {error}
          </div>
        )}

        {loading && <LoadingStatus />}

        {!loading && <ResultsDisplay data={data} />}
      </main>

      <footer className="app__footer">
        Clinical decision support — informational only, not a diagnosis.
      </footer>
    </div>
  );
}
