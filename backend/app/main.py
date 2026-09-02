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
