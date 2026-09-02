from typing import Any, Dict

from fastapi import APIRouter, Request

from app.agent import analyze_labs
from app.schemas import AnalyzeLabsRequest, AnalyzeLabsResponse

router = APIRouter(tags=["labs"])


@router.post("/analyze_labs", response_model=AnalyzeLabsResponse)
async def analyze_labs_endpoint(payload: AnalyzeLabsRequest, request: Request) -> Dict[str, Any]:
    return await analyze_labs(request.app.state.mcp_client, payload.labs)
