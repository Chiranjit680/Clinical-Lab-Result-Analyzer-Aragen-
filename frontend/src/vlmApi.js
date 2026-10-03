/**
 * Client for the VLM agent service (port 8084), which runs a global agent plus
 * a grid of tile agents over one image. Separate from the lab analyzer: that
 * one reads values, this one reads pixels.
 */
const VLM_API_BASE = import.meta.env.VITE_VLM_API_BASE || "http://127.0.0.1:8084";

/**
 * POST /analyze_image -> { answer, global_summary, tiles[], seconds }
 *
 * Content-Type is left unset so the browser supplies the multipart boundary.
 * Slow: tens of model calls per image.
 */
export async function analyzeImage(file, question) {
  const form = new FormData();
  form.append("file", file);
  if (question) form.append("question", question);

  let response;
  try {
    response = await fetch(`${VLM_API_BASE}/analyze_image`, { method: "POST", body: form });
  } catch {
    throw new Error(
      `Cannot reach the VLM service at ${VLM_API_BASE}. Is it running (uvicorn vlm_agents.main:app --port 8084)?`
    );
  }

  if (!response.ok) {
    // FastAPI puts the useful message in `detail`; fall back to the raw body.
    const raw = await response.text();
    let detail = raw;
    try {
      detail = JSON.parse(raw).detail ?? raw;
    } catch {
      /* not JSON — keep the raw body */
    }
    throw new Error(`Image analysis failed (HTTP ${response.status}): ${String(detail).slice(0, 300)}`);
  }
  return response.json();
}
