"""
Gestión de jobs asíncronos (SP-5.3).

Analisis pesados (Signal Lab, Strategy Optimizer, backtest) se ejecutan en
background y el cliente hace polling a /api/jobs/{job_id}.

Estado: running -> done | error. Persistido en Redis (TTL 1h) con fallback
en memoria para entornos sin Redis.
"""

import logging
import os
import threading
import time
import uuid
from typing import Callable, Optional

import redis as redis_lib

logger = logging.getLogger(__name__)

JOB_TTL = 3600  # 1 hora

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

# Fallback en memoria (sin Redis)
_MEMORY_STORE: dict[str, dict] = {}
_MEMORY_LOCK = threading.Lock()


def _get_redis():
    try:
        r = redis_lib.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
        r.ping()
        return r
    except Exception:
        return None


def _job_key(job_id: str) -> str:
    return f"job:{job_id}"


def create_job(job_type: str, params: dict, ttl: int = JOB_TTL) -> str:
    """Crea un job en estado running y devuelve su id."""
    job_id = uuid.uuid4().hex[:12]
    payload = {
        "id": job_id,
        "type": job_type,
        "params": params,
        "status": "running",
        "created_at": time.time(),
    }
    r = _get_redis()
    if r:
        r.setex(_job_key(job_id), ttl, __import__("json").dumps(payload))
    else:
        with _MEMORY_LOCK:
            _MEMORY_STORE[job_id] = payload
    return job_id


def get_job(job_id: str) -> Optional[dict]:
    """Devuelve el estado del job o None si no existe."""
    r = _get_redis()
    if r:
        raw = r.get(_job_key(job_id))
        if not raw:
            return None
        import json
        return json.loads(raw)
    with _MEMORY_LOCK:
        return _MEMORY_STORE.get(job_id)


def _update_job(job_id: str, **fields) -> None:
    job = get_job(job_id)
    if job is None:
        return
    job.update(fields)
    r = _get_redis()
    if r:
        import json
        r.setex(_job_key(job_id), JOB_TTL, json.dumps(job))
    else:
        with _MEMORY_LOCK:
            _MEMORY_STORE[job_id] = job


def mark_job_done(job_id: str, result) -> None:
    _update_job(job_id, status="done", result=result, finished_at=time.time())


def mark_job_error(job_id: str, error: str) -> None:
    _update_job(job_id, status="error", error=error, finished_at=time.time())


def list_jobs(limit: int = 50) -> list[dict]:
    """Lista jobs recientes."""
    r = _get_redis()
    if r:
        keys = r.keys("job:*")[:limit]
        import json
        out = []
        for k in keys:
            raw = r.get(k)
            if raw:
                out.append(json.loads(raw))
        return out
    with _MEMORY_LOCK:
        return sorted(_MEMORY_STORE.values(), key=lambda j: j["created_at"], reverse=True)[:limit]


def run_async_job(job_type: str, params: dict, fn: Callable, ttl: int = JOB_TTL) -> str:
    """Ejecuta fn(params) en un thread background y actualiza el job al terminar."""
    job_id = create_job(job_type, params, ttl=ttl)

    def _worker():
        try:
            result = fn(params)
            mark_job_done(job_id, result)
        except Exception as e:
            logger.error(f"Job {job_id} fallo: {e}")
            mark_job_error(job_id, str(e))

    threading.Thread(target=_worker, daemon=True).start()
    return job_id