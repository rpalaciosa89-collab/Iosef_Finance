from typing import Any, Dict
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.deepseek_client import call_deepseek

router = APIRouter()


class LLMRequest(BaseModel):
    prompt: str


class LLMResponse(BaseModel):
    result: Dict[str, Any]


@router.post("/generate", response_model=LLMResponse)
async def generate(prompt_req: LLMRequest) -> Any:
    try:
        resp = await call_deepseek(prompt_req.prompt)
        return LLMResponse(result=resp)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"DeepSeek request failed: {e}")
