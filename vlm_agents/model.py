"""Vision model access over an OpenAI-compatible API.

Replaces the previous local Qwen2.5-VL load. The agents fan out into a grid of
tile agents plus a global agent, each running its own tool loop, so inference is
better served remotely than by holding a model in GPU memory — and it removes
torch, transformers and a multi-gigabyte checkpoint from the dependency set.

The public surface is unchanged: `get_model().chat(prompt, image, system,
max_new_tokens)`.
"""

import base64
import io
import time

from openai import OpenAI
from PIL import Image

from . import config, logs

log = logs.get("model")

_singleton = None


def _encode(image: Image.Image) -> str:
    """PIL image -> a data URI the chat API will accept.

    Downscaled first: the request body carries the image as base64, which is
    about a third larger again than the raw bytes.
    """
    longest = max(image.size)
    if longest > config.VLM_MAX_IMAGE_SIDE:
        scale = config.VLM_MAX_IMAGE_SIDE / longest
        new_size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
        log.debug("downscaling %s -> %s for transport", image.size, new_size)
        image = image.resize(new_size, Image.LANCZOS)

    # JPEG has no alpha channel, and medical images arrive in assorted modes.
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=config.VLM_JPEG_QUALITY)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


class VlmClient:
    """Thin wrapper over the chat-completions endpoint."""

    def __init__(self, base_url: str = None, api_key: str = None, model: str = None):
        self.model = model or config.VLM_MODEL
        base_url = base_url or config.VLM_BASE_URL
        api_key = api_key or config.VLM_API_KEY

        if not api_key:
            raise RuntimeError(
                "No API key for the vision model. Set VLM_API_KEY (or INFERENCE_API_KEY)."
            )

        self.client = OpenAI(
            base_url=base_url, api_key=api_key, timeout=config.VLM_TIMEOUT_SECONDS
        )
        log.info("vision model %s via %s", self.model, base_url)

    def chat(self, prompt: str, image: Image.Image | None = None,
             system: str | None = None, max_new_tokens=config.MAX_NEW_TOKENS) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})

        if image is None:
            # Plain string rather than a one-element list: some OpenAI-compatible
            # servers reject the structured form on text-only requests.
            messages.append({"role": "user", "content": prompt})
        else:
            messages.append({
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": _encode(image)}},
                    {"type": "text", "text": prompt},
                ],
            })

        # A ceiling, not a spend: only the tokens actually generated are billed,
        # so a generous budget costs nothing on the calls that do not need it.
        budget = max_new_tokens + config.VLM_REASONING_HEADROOM

        last_error = None
        for attempt in range(1, config.VLM_ATTEMPTS + 1):
            t0 = time.perf_counter()
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    # Reasoning happens inside this budget and is not returned,
                    # so the caller's figure is topped up rather than used as-is.
                    # Without the headroom the answer comes back empty.
                    max_tokens=budget,
                    # Deterministic, matching the previous do_sample=False.
                    temperature=0,
                )
            except Exception as exc:
                last_error = exc
                log.warning("attempt %d/%d failed after %.1fs: %s: %s", attempt,
                            config.VLM_ATTEMPTS, time.perf_counter() - t0,
                            type(exc).__name__, str(exc)[:200])
                continue

            dt = time.perf_counter() - t0
            usage = getattr(response, "usage", None)
            details = getattr(usage, "completion_tokens_details", None)
            # Reasoning tokens are logged because they are the usual explanation
            # for a short or empty answer.
            # INFO, not DEBUG: one line per model call is the finest-grained
            # view of a run that is useful without drowning the output.
            log.info("model call: %s prompt / %s completion (%s reasoning) of %d budget "
                     "in %.1fs, image=%s",
                     getattr(usage, "prompt_tokens", "?"),
                     getattr(usage, "completion_tokens", "?"),
                     getattr(details, "reasoning_tokens", "?"),
                     budget, dt, image.size if image is not None else None)

            text = (response.choices[0].message.content or "").strip()
            if text:
                return text

            # Empty content means hidden reasoning consumed the whole budget
            # before any answer was emitted. Re-sending the identical request
            # would fail identically, so the next attempt gets a bigger budget
            # — that is the only thing that can change the outcome.
            last_error = RuntimeError(
                f"model returned empty content: reasoning used the whole {budget}-token budget"
            )
            log.warning("attempt %d/%d returned no content after %.1fs (budget %d)",
                        attempt, config.VLM_ATTEMPTS, dt, budget)
            budget *= 2

        raise RuntimeError(f"Vision model call failed after {config.VLM_ATTEMPTS} attempts: {last_error}")


def get_model() -> VlmClient:
    global _singleton
    if _singleton is None:
        _singleton = VlmClient()
    return _singleton
