# Gestión de Cambios (Changelog)

Registro estricto de los cambios importantes en el ecosistema Iosef Finance.

## [Unreleased]
### Added
- `docs/` con 4 archivos: `registro_conversacion.md`, `mejores_practicas.md`, `aprendizajes.md`, `gestion_cambios.md`.
- `agents/system_prompts_equipo.md` con definición de Raymond, Javier, Luis y Carlos.
- `backend/app/services/__init__.py` — paquete de dominio bajo Clean Architecture.
- `backend/tests/` — suite inicial de pytest con 12 tests unitarios para `scoring.py`.
- `backend/tests/test_scoring.py` — **12/12 PASSED ✅**.

### Changed
- Migración de servicios sueltos (`analytics.py`, `persistence.py`, `scoring.py`, `human_layer.py`, `signal_evaluation.py`, `strategy_optimizer.py`) al paquete `backend/app/services/`.
- Actualización de importaciones en `server.py` y `strategy_optimizer.py` para respetar la nueva estructura de módulos.

### Fixed
- `backend/app/config.py`: `extra="ignore"` en Pydantic para evitar crash al arrancar con variables de entorno adicionales.

### Discovered Issues (Carlos)
- yfinance reporta 3 tickers potencialmente delisted: **WBA**, **SPLK**, **ANSS**. Deben ser depurados de los universos `NASDAQ100_TICKERS` y `SP500_TICKERS`.

### Pending
- Migración del frontend `index.html` (180KB monolítico) a React + Vite.
- Tests de endpoints HTTP y auditoría de seguridad (Luis).
- Auditoría cuantitativa del motor de scoring (Carlos).
