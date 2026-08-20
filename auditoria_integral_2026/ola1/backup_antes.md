# Ola 1 — Backup del estado antes de cambios

**Fecha:** 2026-06-09
**Archivos a modificar:**
- `backend/app/core/security.py`
- `backend/app/config.py`
- `backend/server.py`
- `docker-compose.yml`
- `backend/.env.example`
- `.gitignore`

## security.py (línea 7)
```python
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7")
```
- Secreto hardcodeado visible en el repositorio
- No hay validación de que la variable esté configurada

## config.py (línea 22)
```python
SECRET_KEY: str = "change_me_to_a_secure_random_key_in_production"
```
- Nombre `SECRET_KEY` inconsistente con `JWT_SECRET_KEY` de `security.py`
- Fallback inseguro diferente

## server.py (líneas 998-1004)
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```
- CORS abierto a cualquier origen con credenciales

## docker-compose.yml (backend service)
```yaml
environment:
  - REDIS_HOST=redis
  - REDIS_PORT=6379
```
- Solo Redis configurado, sin JWT_SECRET_KEY, CORS_ORIGINS, DATABASE_URL

## .env.example
- Incluye `SECRET_KEY` pero no `JWT_SECRET_KEY` ni `CORS_ORIGINS`

## .gitignore
- Protege `data/*.db` pero NO `backend/*.db` ni `*.db` en raíz
