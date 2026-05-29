import hashlib
import json
from typing import Any, Dict, Optional
import httpx
from app.config import settings


# Shared HTTP client with connection pooling (reuses connections across calls)
_client: Optional[httpx.AsyncClient] = None

# Simple in-memory response cache (prompt hash → response)
_response_cache: Dict[str, Dict[str, Any]] = {}
_RESPONSE_CACHE_MAX = 256


def _get_client() -> httpx.AsyncClient:
    """Return a singleton AsyncClient with connection pooling."""
    global _client
    if _client is None or _client.is_closed:
        limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
        _client = httpx.AsyncClient(timeout=30.0, limits=limits)
    return _client


def _prompt_hash(prompt: str, model: str) -> str:
    """Hash prompt + model for cache key (fast, deterministic)."""
    return hashlib.sha256(f"{model}|{prompt}".encode()).hexdigest()


async def call_deepseek(
    prompt: str,
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    timeout: Optional[int] = None,
    use_cache: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Optimized async client to call DeepSeek HTTP API.

    Control de costos:
      - max_tokens:  menor → más barato  (default: config.DEEPSEEK_MAX_TOKENS)
      - temperature: 0.0 → determinista  (barato, consistente)
                     0.7 → creativo      (caro)
      - use_cache:   True → respuestas duplicadas no consumen API

    Configure `DEEPSEEK_API_URL` and `DEEPSEEK_API_KEY` in the `.env`.
    """
    model      = model      or settings.DEEPSEEK_MODEL
    max_tokens = max_tokens or settings.DEEPSEEK_MAX_TOKENS
    temperature = temperature if temperature is not None else settings.DEEPSEEK_TEMPERATURE
    timeout    = timeout    or settings.DEEPSEEK_TIMEOUT
    use_cache  = use_cache  if use_cache is not None else settings.DEEPSEEK_USE_CACHE

    # Cache check (avoid redundant API calls for identical prompts)
    if use_cache:
        key = _prompt_hash(prompt, model)
        if key in _response_cache:
            return _response_cache[key]

    base_url = settings.DEEPSEEK_API_URL.rstrip("/")
    # DeepSeek usa formato compatible con OpenAI Chat Completions
    endpoint = f"{base_url}/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    headers = {"Content-Type": "application/json"}
    if settings.DEEPSEEK_API_KEY:
        headers["Authorization"] = f"Bearer {settings.DEEPSEEK_API_KEY}"

    client = _get_client()
    resp = await client.post(endpoint, json=payload, headers=headers, timeout=timeout)
    resp.raise_for_status()
    result = resp.json()

    # Store in cache (with LRU-like eviction)
    if use_cache:
        key = _prompt_hash(prompt, model)
        if len(_response_cache) >= _RESPONSE_CACHE_MAX:
            # Evict oldest entry
            _response_cache.pop(next(iter(_response_cache)))
        _response_cache[key] = result

    return result


async def close_client() -> None:
    """Gracefully close the shared HTTP client (call on app shutdown)."""
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None
