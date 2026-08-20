import os
import sys

import pytest
from sqlalchemy import create_engine, text


def test_sqlite_wal_mode():
    """La DB SQLite debe correr en journal_mode=WAL (SP-3.4)."""
    from app.config import settings

    engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})
    with engine.connect() as conn:
        rows = conn.execute(text("PRAGMA journal_mode")).fetchone()
    assert rows[0].lower() == "wal"
    engine.dispose()


def test_alembic_has_initial_migration():
    """Debe existir una migración inicial versionada por Alembic."""
    versions_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "alembic", "versions"
    )
    assert os.path.isdir(versions_dir)
    revisions = [f for f in os.listdir(versions_dir) if f.endswith(".py")]
    assert len(revisions) >= 1


def test_alembic_config_exists():
    ini = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "alembic.ini")
    env = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "alembic",
        "env.py",
    )
    assert os.path.exists(ini)
    assert os.path.exists(env)


def test_alembic_no_drift_on_test_db():
    """alembic check no debe detectar operaciones pendientes (0 drift)."""
    import subprocess

    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = os.environ.copy()
    env["DATABASE_URL"] = "sqlite:////tmp/alembic_drift_check.db"
    if os.path.exists("/tmp/alembic_drift_check.db"):
        os.remove("/tmp/alembic_drift_check.db")
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend_dir,
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "check"],
        cwd=backend_dir,
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr