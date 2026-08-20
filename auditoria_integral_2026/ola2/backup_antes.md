# Ola 2 — Backup del estado post-Ola-1

**Fecha:** 2026-06-09
**Archivos a modificar:**
- `backend/server.py` — agregar health endpoint y validación ticker
- `frontend-v2/src/tabs/Analytics.tsx` — corregir bug URL
- `docker-compose.yml` — agregar healthchecks
- `README.md` — actualizar

## Estado actual de archivos clave

### server.py — health endpoint: NO existe
No hay endpoint `/api/health`.

### server.py — validación ticker: NO existe
No hay validación regex en parámetros de ruta que reciben ticker.

### Analytics.tsx — bug confirmado
Línea con `&_t=` que debe ser `?_t=`.

### docker-compose.yml — healthchecks: NO existen
Post-Ola-1 tiene variables de entorno pero sin healthchecks.

### README.md — desactualizado
Menciona `frontend/` y `realtime/` como módulos inexistentes.
Instruye `fastapi dev app/main.py` en lugar de `server.py`.
