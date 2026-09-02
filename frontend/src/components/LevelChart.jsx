import { severityKey } from "./SeverityBadge";

/**
 * Each test is plotted against ITS OWN reference range, not a shared value axis —
 * the panel mixes g/dL, 10^3/uL, %, mIU/L, so one value axis would be meaningless.
 * Normalising every test to its own range (min -> 0, max -> 1) makes "how far
 * outside normal" the comparable quantity across rows.
 *
 * Domain is [-0.5, 1.5] of that normalised space, so the normal band occupies the
 * middle half and out-of-range values still have room to show on either side.
 */
const DOMAIN_MIN = -0.5;
const DOMAIN_MAX = 1.5;

const toPercent = (norm) => ((norm - DOMAIN_MIN) / (DOMAIN_MAX - DOMAIN_MIN)) * 100;

const BAND_START = toPercent(0); // 25%
const BAND_WIDTH = toPercent(1) - BAND_START; // 50%

/** Status is carried by shape as well as colour, so it survives colour-blindness. */
function MarkerShape({ status }) {
  const key = severityKey(status);
  if (key === "critical") {
    // Triangle — the most visually urgent silhouette.
    return <polygon points="7,1 13.5,12.5 0.5,12.5" />;
  }
  if (key === "warning") {
    return <polygon points="7,0.5 13.5,7 7,13.5 0.5,7" />; // diamond
  }
  return <circle cx="7" cy="7" r="5.5" />;
}

function parseRange(result) {
  // reference_range is rendered as "12.0-15.0 g/dL"; pull the two numbers back out.
  const match = String(result.reference_range || "").match(
    /(-?\d+(?:\.\d+)?)\s*-\s*(-?\d+(?:\.\d+)?)/
  );
  if (!match) return null;
  const low = Number(match[1]);
  const high = Number(match[2]);
  if (!Number.isFinite(low) || !Number.isFinite(high) || high <= low) return null;
  return { low, high };
}

function buildRow(result) {
  const value = Number(result.value);
  if (!Number.isFinite(value)) return null; // qualitative ("Negatif", "1+")
  const range = parseRange(result);
  if (!range) return null; // Unknown tests have no range to plot against

  const norm = (value - range.low) / (range.high - range.low);
  const clamped = norm < DOMAIN_MIN || norm > DOMAIN_MAX;
  const shown = Math.min(DOMAIN_MAX, Math.max(DOMAIN_MIN, norm));

  return { result, value, range, clamped, left: toPercent(shown) };
}

export default function LevelChart({ data }) {
  if (!data?.results) return null;

  const all = ["critical", "warning", "unknown", "normal"].flatMap(
    (bucket) => data.results[bucket] || []
  );
  const rows = all.map(buildRow).filter(Boolean);
  const skipped = all.length - rows.length;

  if (!rows.length) return null;

  return (
    <section className="lc">
      <header className="lc__head">
        <h2>Comparison with normal range</h2>
        <div className="lc__legend">
          {[
            { key: "normal", label: "Normal" },
            { key: "warning", label: "Warning" },
            { key: "critical", label: "Critical" },
          ].map(({ key, label }) => (
            <span className="lc__legend-item" key={key}>
              <svg className={`lc__swatch lc__swatch--${key}`} viewBox="0 0 14 14" aria-hidden="true">
                <MarkerShape status={key} />
              </svg>
              {label}
            </span>
          ))}
        </div>
      </header>

      <p className="lc__caption">
        Each test is scaled to its own reference range, so the shaded band means “normal” for every
        row. Distance from that band shows how far outside normal a result sits.
      </p>

      <div className="lc__rows">
        {rows.map(({ result, value, range, clamped, left }, i) => {
          const key = severityKey(result.status);
          const detail = `${result.test_name}: ${value} ${result.unit || ""} (normal ${range.low}–${range.high})`;
          return (
            <div className="lc__row" key={`${result.test_name}-${i}`}>
              <div className="lc__label" title={result.test_name}>
                {result.test_name}
              </div>

              <div className="lc__track" tabIndex={0} aria-label={detail}>
                <div className="lc__band" style={{ left: `${BAND_START}%`, width: `${BAND_WIDTH}%` }} />
                <span className="lc__edge" style={{ left: `${BAND_START}%` }} />
                <span className="lc__edge" style={{ left: `${BAND_START + BAND_WIDTH}%` }} />

                <svg
                  className={`lc__marker lc__marker--${key}${clamped ? " lc__marker--clamped" : ""}`}
                  style={{ left: `${left}%` }}
                  viewBox="0 0 14 14"
                  aria-hidden="true"
                >
                  <MarkerShape status={result.status} />
                </svg>

                <div className="lc__tip" role="tooltip">
                  <strong>
                    {value} {result.unit}
                  </strong>
                  <span>
                    normal {range.low}–{range.high} {result.unit}
                  </span>
                  {result.deviation && <span>{result.deviation}</span>}
                  {clamped && <span>far outside range — pinned to edge</span>}
                </div>
              </div>

              <div className={`lc__value lc__value--${key}`}>
                {value}
                <span className="lc__unit"> {result.unit}</span>
              </div>
            </div>
          );
        })}
      </div>

      <div className="lc__axis">
        <span style={{ left: `${BAND_START}%` }}>range min</span>
        <span style={{ left: `${BAND_START + BAND_WIDTH}%` }}>range max</span>
      </div>

      {skipped > 0 && (
        <p className="lc__note">
          {skipped} result{skipped === 1 ? "" : "s"} not plotted — qualitative values (e.g. “Negatif”,
          “1+”) or tests with no numeric reference range.
        </p>
      )}
    </section>
  );
}
