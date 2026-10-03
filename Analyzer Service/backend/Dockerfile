# Analyzer Service — FastAPI + LangGraph + MCP tool server.
#
# Build context is this directory (Analyzer Service/backend), not the repo root:
#   docker build -t analyzer-service "Analyzer Service/backend"

FROM python:3.12-slim

# Unbuffered so logs reach the platform live rather than sitting in a buffer;
# no .pyc files since the layer is read-only in practice.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# WORKDIR is the backend root, not the package directory. mcp_client.py spawns
# the tool server as `sys.executable -m app.mcp_server`, so `app` has to be
# importable from the working directory or that subprocess fails at startup.
WORKDIR /app

# Dependencies in their own layer: rebuilt only when requirements.txt changes,
# not on every source edit.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# 0.0.0.0 because a container that binds loopback is unreachable from outside
# it. PORT is overridden by most platforms (Render injects its own).
ENV HOST=0.0.0.0 \
    PORT=8000

EXPOSE 8000

# Unprivileged user. /app must stay writable: the run-log middleware creates
# logs/runs.csv relative to the working directory.
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/logs \
    && chown -R appuser:appuser /app
USER appuser

HEALTHCHECK --interval=30s --timeout=5s --start-period=45s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT','8000') + '/health')"

# uvicorn is invoked directly rather than through `python -m app.main`: that
# entry point defaults to host 127.0.0.1 and switches on the autoreloader,
# neither of which belongs in a container.
CMD ["sh", "-c", "exec uvicorn app.main:app --host \"$HOST\" --port \"$PORT\""]
