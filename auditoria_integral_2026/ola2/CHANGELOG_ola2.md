# Ola 2 — Higiene Operativa — CHANGELOG

**Fecha:** 2026-06-09
**Ejecutor:** Auditor Integral de Plataforma Financiera (Agente)
**Duración real:** ~1.5 horas
**Duración estimada:** ~3 horas

---

## Resumen

Agregados health endpoints, validación de inputs, corregido bug de Analytics, actualizado README y Docker Compose con healthchecks.

## Hallazgos Resueltos

| ID | Severidad | Descripción | Estado |
|---|---|---|---|
| H-019 | Baja | Sin healthchecks en Docker Compose ni endpoint | ✅ Resuelto |
| H-011 | Media | Bug de URL en Analytics (`&_t` → `?_t`) | ✅ Resuelto |
| H-016 | Baja | README desactualizado | ✅ Resuelto |
| QA | Media | Sin validación regex en parámetros ticker | ✅ Resuelto |

## Pasos Ejecutados

### Paso 2.0 — Backup ✅
- Documentado en `auditoria_integral_2026/ola2/backup_antes.md`

### Paso 2.1 — Health endpoint ✅
- **Archivo:** `backend/server.py`
- Agregado `GET /api/health` → `{"status":"ok","service":"iosef-backend"}`
- Colocado después del startup event, antes de los endpoints principales

### Paso 2.2 — Bug Analytics URL ✅
- **Archivo:** `frontend-v2/src/tabs/Analytics.tsx`
- Línea 21: `&_t=` → `?_t=`
- URL ahora correctamente formada: `/api/analytics?_t=...`

### Paso 2.3 — Validación regex ticker ✅
- **Archivos:** `backend/app/core/validators.py` (nuevo), `backend/server.py`
- Creado validador reutilizable con regex `^[A-Za-z0-9\.\-]{1,10}$`
- `get_ticker_financials` ahora tiene validación vía `Path(pattern=...)`
- Las otras 3 rutas de ticker ya tenían validación
- Path traversal e inyección son rechazados (HTTP 404)

### Paso 2.4 — Healthchecks Docker Compose ✅
- **Archivo:** `docker-compose.yml`
- Redis: `redis-cli ping` cada 10s
- Backend: Python urllib a `/api/health` cada 30s, start_period 15s
- Frontend: `wget --spider` a `localhost:80` cada 30s
- `depends_on` actualizado a `condition: service_healthy`

### Paso 2.5 — Actualizar README ✅
- **Archivo:** `README.md`
- Eliminados módulos inexistentes (`frontend/`, `realtime/`)
- Agregado `frontend-v2/` real
- Entrypoint correcto: `uvicorn server:app`
- Nueva sección "Variables de Entorno Requeridas"
- Instrucciones Docker + Desarrollo Local

### Paso 2.6 — Verificación de regresión ✅
- 33/33 tests unitarios pasan
- Health endpoint responde 200 con JSON
- Tickers válidos aceptados, path traversal rechazado
- Registro, login y endpoints protegidos funcionales
- Frontend TypeScript compila sin errores nuevos

## Archivos Modificados

| Archivo | Cambio |
|---|---|
| `backend/server.py` | Health endpoint + validación ticker en financials |
| `frontend-v2/src/tabs/Analytics.tsx` | Bugfix `&_t` → `?_t` |
| `backend/app/core/validators.py` | **Nuevo** — validador ticker |
| `docker-compose.yml` | Healthchecks + `condition: service_healthy` |
| `README.md` | Estructura real, entrypoint correcto, Docker, env vars |

## Problemas Encontrados

Ninguno. Todos los CHECKs pasaron a la primera.

## Ajustes al Plan de Olas Siguientes

Ninguno. Ola 3 puede ejecutarse según lo planeado.

## Score

| Dimensión | Antes (post-Ola 1) | Después |
|---|---|---|
| Operabilidad | 4/10 | 6/10 |
| Documentación | 5/10 | 7/10 |
| **Global** | **5/10** | **6/10** |

---

*Ola 2 completada exitosamente.*
