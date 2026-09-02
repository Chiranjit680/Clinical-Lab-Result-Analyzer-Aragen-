import { useEffect, useState } from "react";

/**
 * Messages mirror the real backend pipeline order
 * (validate -> translate -> classify -> route -> search -> explain -> next steps),
 * so the wait tells the user what the agent is actually doing.
 *
 * These are time-based, not progress events from the server — the last message
 * is deliberately open-ended so it stays honest if a step runs long.
 */
const STAGES = [
  "Validating lab records…",
  "Translating source fields to English…",
  "Comparing values against reference ranges…",
  "Grouping results by severity…",
  "Searching PubMed for clinical context…",
  "Writing clinical explanations…",
  "Preparing suggested next steps…",
  "Finishing up — this can take a moment for large panels…",
];

const STEP_MS = 3500;

export default function LoadingStatus() {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      // Hold on the final message rather than looping, so it never looks
      // like the run restarted.
      setIndex((i) => (i < STAGES.length - 1 ? i + 1 : i));
    }, STEP_MS);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="loading" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      <div className="loading__body">
        <p className="loading__stage">{STAGES[index]}</p>
        <div className="loading__track" aria-hidden="true">
          <div
            className="loading__bar"
            style={{ width: `${((index + 1) / STAGES.length) * 100}%` }}
          />
        </div>
        <p className="loading__note">
          Abnormal results are researched before they are explained, so this takes longer than a
          plain lookup.
        </p>
      </div>
    </div>
  );
}
