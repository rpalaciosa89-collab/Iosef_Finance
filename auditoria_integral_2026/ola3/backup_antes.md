# Ola 3 — Backup del estado post-Ola-2

**Fecha:** 2026-06-09
**Archivos a crear/modificar:**
- `.github/workflows/ci.yml` (nuevo) — GitHub Actions pipeline
- `backend/tests/test_api/test_auth.py` (nuevo) — tests integración auth
- `backend/tests/test_api/test_paper_trading.py` (nuevo) — tests integración paper trading
- `backend/tests/conftest.py` (nuevo) — fixtures compartidos
- `frontend-v2/src/__tests__/` (nuevo) — tests Vitest
- `frontend-v2/package.json` — agregar dependencias vitest
- `frontend-v2/vite.config.ts` — configurar test environment

## Estado actual

### Testing backend
- 33 tests unitarios (scoring + signal_evaluation)
- 0 tests de integración HTTP
- 0 tests de frontend

### CI/CD
- No existe `.github/workflows/`
- No hay pipeline automatizado

### Frontend testing
- Sin vitest/jest instalado
- Sin tests de componentes/hooks
