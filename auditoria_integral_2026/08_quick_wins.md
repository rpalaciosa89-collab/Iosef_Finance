# 9. Quick Wins

Mejoras de alto impacto y bajo esfuerzo que pueden implementarse en un solo sprint.

---

## QW-1: Eliminar JWT secret hardcodeado

**Esfuerzo:** Bajo | **Impacto:** Crítico | **Hallazgo:** H-002

Cambiar [security.py:L7](file:///Users/raymondpalacios/Documents/Bootcamp%20Data%20Science/Iosef_Finance/backend/app/core/security.py#L7) de:
```python
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "09d25e094faa...")
```
a:
```python
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY environment variable is required")
```

---

## QW-2: Restringir CORS

**Esfuerzo:** Bajo | **Impacto:** Alto | **Hallazgo:** H-004

Cambiar [server.py:L998-L1004](file:///Users/raymondpalacios/Documents/Bootcamp%20Data%20Science/Iosef_Finance/backend/server.py#L998-L1004) de `allow_origins=["*"]` a una lista explícita leída de variable de entorno:
```python
origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
app.add_middleware(CORSMiddleware, allow_origins=origins, ...)
```

---

## QW-3: Corregir URL de Analytics

**Esfuerzo:** Bajo | **Impacto:** Medio | **Hallazgo:** H-011

Cambiar `&_t=` por `?_t=` en [Analytics.tsx:L20-L25](file:///Users/raymondpalacios/Documents/Bootcamp%20Data%20Science/Iosef_Finance/frontend-v2/src/tabs/Analytics.tsx#L20-L25).

---

## QW-4: Unificar configuración JWT

**Esfuerzo:** Bajo | **Impacto:** Medio | **Hallazgo:** H-010

Hacer que `security.py` importe `SECRET_KEY` de `config.py` en lugar de definir su propia variable.

---

## QW-5: Agregar health endpoint

**Esfuerzo:** Bajo | **Impacto:** Medio | **Hallazgo:** H-019

Agregar en `server.py`:
```python
@app.get("/api/health")
def health():
    return {"status": "ok"}
```

---

## QW-6: Proteger archivos .db en .gitignore

**Esfuerzo:** Bajo | **Impacto:** Bajo | **Hallazgo:** H-017

Agregar a `.gitignore`:
```
backend/*.db
*.db
!data/.gitkeep
```

---

## QW-7: Inyectar JWT_SECRET_KEY en docker-compose

**Esfuerzo:** Bajo | **Impacto:** Crítico | **Hallazgo:** H-020

Agregar al servicio backend en `docker-compose.yml`:
```yaml
environment:
  - JWT_SECRET_KEY=${JWT_SECRET_KEY}
```

---

## QW-8: Agregar healthchecks en Docker Compose

**Esfuerzo:** Bajo | **Impacto:** Medio | **Hallazgo:** H-019

```yaml
redis:
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]
    interval: 10s

backend:
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8002/api/health"]
    interval: 30s
```

---

## QW-9: Actualizar README

**Esfuerzo:** Bajo | **Impacto:** Bajo | **Hallazgo:** H-016

Actualizar la estructura del proyecto y las instrucciones de arranque para reflejar `frontend-v2/` y `server.py` como entrada canónica.

---

## QW-10: Validar parámetro ticker con regex

**Esfuerzo:** Bajo | **Impacto:** Medio | **Hallazgo:** QA Report

Agregar validación regex `^[A-Z0-9\.\-]{1,10}$` en los parámetros de ruta que aceptan tickers.

---

**Total estimado:** ~2-3 días de desarrollo para completar los 9 quick wins.
