# 8. Roadmap Recomendado

---

## Acciones Inmediatas (Sprint actual)

| # | Acción | Hallazgo | Esfuerzo |
|---|---|---|---|
| 1 | Eliminar JWT secret hardcodeado. Lanzar error si no configurado | H-002 | Bajo |
| 2 | Inyectar `JWT_SECRET_KEY` en docker-compose.yml | H-002, H-020 | Bajo |
| 3 | Restringir CORS a orígenes explícitos, quitar `allow_credentials=True` si `*` | H-004 | Bajo |
| 4 | Corregir bug de URL en Analytics (`&_t` → `?_t`) | H-011 | Bajo |
| 5 | Unificar configuración JWT (`security.py` debe leer de `config.py`) | H-010 | Bajo |
| 6 | Agregar `backend/*.db` a `.gitignore` | H-017 | Bajo |
| 7 | Agregar health endpoint `/api/health` al backend | H-019 | Bajo |

---

## Corto Plazo (Próximo sprint)

| # | Acción | Hallazgo | Esfuerzo |
|---|---|---|---|
| 8 | Unificar backend en un solo entrypoint (`server.py` como canónico) | H-001 | Medio |
| 9 | Centralizar URLs de API en frontend con `VITE_API_BASE` | H-006 | Medio |
| 10 | Crear cliente HTTP centralizado en frontend (`src/lib/api.ts`) | H-006 | Medio |
| 11 | Crear pipeline CI/CD (GitHub Actions: pytest + eslint + build) | H-005 | Medio |
| 12 | Agregar tests de integración HTTP para auth y paper trading | H-009 | Medio |
| 13 | Instalar Vitest + @testing-library/react, crear primeros tests | H-007 | Medio |
| 14 | Agregar healthchecks a Docker Compose (Redis, backend, frontend) | H-019 | Bajo |
| 15 | Migrar token JWT a cookie HttpOnly (o reducir TTL a 15 min) | H-008 | Medio |

---

## Medio Plazo (2-4 sprints)

| # | Acción | Hallazgo | Esfuerzo |
|---|---|---|---|
| 16 | Reentrenar XGBoost con datos reales de `trades_history.db` | H-003 | Alto |
| 17 | Implementar validación cruzada temporal para ML | H-003 | Alto |
| 18 | Mover operaciones bloqueantes a background tasks / run_in_executor | H-014 | Medio |
| 19 | Unificar persistencia en una sola base de datos (SQLAlchemy) | H-015 | Alto |
| 20 | Implementar WebSocket para datos en tiempo real | H-013 | Medio |
| 21 | Agregar rate limiting a endpoints de auth | — | Medio |
| 22 | Agregar monitoreo de drift para modelos ML | — | Alto |
| 23 | Implementar logging estructurado (JSON) | — | Medio |
| 24 | Migrar estilos inline a CSS Modules | H-018 | Medio |
| 25 | Eliminar tipos `any` del frontend | H-018 | Medio |

---

## Largo Plazo (4+ sprints)

| # | Acción | Esfuerzo |
|---|---|---|
| 26 | Migrar SQLite a PostgreSQL | Alto |
| 27 | Agregar métricas de aplicación (Prometheus + Grafana) | Alto |
| 28 | Implementar refresh token con rotación | Medio |
| 29 | Tests E2E con Playwright | Alto |
| 30 | Tests de carga con k6 | Medio |
| 31 | Implementar secrets management (Vault o AWS Secrets Manager) | Alto |
| 32 | Agregar CD (deploy automatizado a staging/producción) | Alto |
| 33 | Implementar blue/green o canary deployments | Alto |
| 34 | Agregar APM (Sentry/DataDog) para monitoreo de errores | Medio |
| 35 | Abstraer `yfinance` para soportar múltiples proveedores de datos | Alto |
