from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.mcp_client import MCPToolClient
from app.routers import health, labs


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.mcp_client = MCPToolClient()
    await app.state.mcp_client.start()
    yield
    await app.state.mcp_client.stop()


app = FastAPI(title="Results Analyzer", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(labs.router)


def main() -> None:
    """Run with: `python -m app.main` from the `backend/` directory (not `backend/app/`) —
    the `app.` package imports throughout this codebase need `backend/` on sys.path."""
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    main()
