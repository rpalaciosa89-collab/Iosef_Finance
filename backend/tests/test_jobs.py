import time

import pytest

from app.services.jobs import (
    create_job,
    get_job,
    mark_job_done,
    mark_job_error,
    list_jobs,
    run_async_job,
)


@pytest.fixture
def redis_backend(monkeypatch):
    """Backend de Redis real si esta disponible; si no, fallback en memoria."""
    try:
        import redis as redis_lib

        r = redis_lib.Redis(host="localhost", port=6379, db=15, decode_responses=True)
        r.ping()
        monkeypatch.setattr("app.services.jobs._get_redis", lambda: r)
        yield r
        r.flushdb()
    except Exception:
        pytest.skip("Redis no disponible")


def test_create_and_get_job(redis_backend):
    job_id = create_job("signal-evaluation", {"market": "titan100"})
    assert job_id is not None
    job = get_job(job_id)
    assert job["status"] == "running"
    assert job["type"] == "signal-evaluation"
    assert job["params"] == {"market": "titan100"}


def test_mark_done_flow(redis_backend):
    job_id = create_job("strategy-optimization", {})
    mark_job_done(job_id, {"result": "ok"})
    job = get_job(job_id)
    assert job["status"] == "done"
    assert job["result"] == {"result": "ok"}


def test_mark_error_flow(redis_backend):
    job_id = create_job("backtest", {"ticker": "AAPL"})
    mark_job_error(job_id, "yfinance rate limited")
    job = get_job(job_id)
    assert job["status"] == "error"
    assert "rate limited" in job["error"]


def test_list_jobs(redis_backend):
    create_job("a", {})
    create_job("b", {})
    jobs = list_jobs()
    assert len(jobs) >= 2
    assert all(j["status"] in ("running", "done", "error") for j in jobs)


def test_get_unknown_job(redis_backend):
    assert get_job("no-existe") is None


def test_run_async_job(redis_backend):
    """run_async_job ejecuta en background y deja el resultado listo."""
    def slow_fn(params):
        time.sleep(0.05)
        return {"echo": params}

    job_id = run_async_job("test-job", {"x": 1}, slow_fn)
    time.sleep(0.3)
    job = get_job(job_id)
    assert job["status"] == "done"
    assert job["result"] == {"echo": {"x": 1}}