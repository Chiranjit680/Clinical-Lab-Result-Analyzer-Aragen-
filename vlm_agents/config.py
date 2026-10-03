import os

from dotenv import load_dotenv

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# Loaded by explicit path, not by searching upwards from the working directory:
# the service is started from the repository root so that `python -m
# vlm_agents.mcp_server` resolves, and a bare load_dotenv() would look there and
# miss this file. Existing environment variables still win, so a deployment can
# override the file without editing it.
load_dotenv(os.path.join(HERE, ".env"))

# ---------------------------------------------------------------------------
# Vision model
#
# Served over an OpenAI-compatible API rather than loaded locally: the agents
# fan out into a grid of tile agents plus a global agent, which is a lot of
# forward passes to run on one machine.
# ---------------------------------------------------------------------------

# Same endpoint the analyzer uses, so one credential and one provider cover
# both services.
VLM_BASE_URL = (
    os.environ.get("VLM_BASE_URL")
    or os.environ.get("INFERENCE_BASE_URL")
    or "https://api.hpc-ai.com/inference/v1"
)

VLM_API_KEY = os.environ.get("VLM_API_KEY") or os.environ.get("INFERENCE_API_KEY", "")

# GLM flash, as served by that endpoint. Must be vision-capable: the global and
# tile agents always send an image.
VLM_MODEL = os.environ.get("VLM_MODEL", "zai-org/glm-5.3-flash")

# Each attempt is a network call; a transient failure should not sink a run that
# has already paid for several tiles.
# The tool server is a subprocess over stdio. If it dies at import there is
# nothing to wait for, so the wait is bounded rather than indefinite.
MCP_START_TIMEOUT = float(os.environ.get("MCP_START_TIMEOUT", "30"))

VLM_ATTEMPTS = int(os.environ.get("VLM_ATTEMPTS", "2"))
VLM_TIMEOUT_SECONDS = float(os.environ.get("VLM_TIMEOUT_SECONDS", "120"))

# Images are base64-encoded into the request body, so an unbounded side length
# turns into an unbounded payload. The agents already downscale and tile before
# reaching here; this is a backstop.
VLM_MAX_IMAGE_SIDE = int(os.environ.get("VLM_MAX_IMAGE_SIDE", "1024"))
VLM_JPEG_QUALITY = int(os.environ.get("VLM_JPEG_QUALITY", "90"))

# GLM-5.3 is a reasoning model: it spends tokens on hidden thinking before
# emitting any answer, and a measured call used 104 of 118 completion tokens
# that way. Budget the answer and the thinking separately, so a caller asking
# for a 384-token answer still gets one instead of an empty string.
#
# Set high because max_tokens is a ceiling rather than a spend: unused budget is
# not billed, while too small a one costs a whole call. The aggregator is the
# call that needs it — it reasons over the global summary and every tile report
# at once, and 1024 was not enough for that.
VLM_REASONING_HEADROOM = int(os.environ.get("VLM_REASONING_HEADROOM", "3072"))

# ---------------------------------------------------------------------------
# Agent fan-out
# ---------------------------------------------------------------------------

GLOBAL_MAX_SIDE = 768      # longest side of the image shown to the global agent
# Tiles per side: 2 -> a 2x2 grid, so four tile agents and one graph node each.
# Every tile is its own tool loop, so this squares the cost of a run: the grid
# is the main dial for how much a single image is worth spending. Fewer tiles
# also means each one covers more area at lower magnification, which the agents
# offset by zooming.
TILE_GRID = int(os.environ.get("TILE_GRID", "2"))
TILE_OVERLAP = 0.15        # fraction of a tile overlapped with its neighbours
# Tool calls allowed per agent before it must answer. Each one costs a model
# call to decide it and another to read the result, so the per-agent call
# count is this plus one.
MAX_TOOL_STEPS = int(os.environ.get("MAX_TOOL_STEPS", "2"))
MAX_NEW_TOKENS = 512     # answer budget; reasoning headroom is added on top
