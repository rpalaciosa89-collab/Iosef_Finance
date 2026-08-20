# Ola 4 — Backup del estado post-Ola-3

**Fecha:** 2026-06-10

## Estado actual

### server.py (~1400 líneas)
- Entrypoint real (Docker)
- Mezcla configuración, background tasks, Redis helpers, y endpoints
- CORS restringido (desde Ola 1)
- Health endpoint (desde Ola 2)
- Validación ticker (desde Ola 2)
- Routers montados: auth, backtest, paper_trading

### app/main.py
- Entrypoint alternativo (nunca usado en Docker)
- Monta routers: auth, backtest, paper_trading, market, screener, llm
- Prefijo /api/v1 (vs /api en server.py)

### Frontend
- URLs hardcodeadas en ~9 componentes
- Sin cliente HTTP centralizado
- Sin variable VITE_API_BASE
