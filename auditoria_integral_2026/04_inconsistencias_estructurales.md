# 5. Inconsistencias Estructurales

---

## 5.1 Diferencias entre `server.py` y `app/main.py`

| Aspecto | `server.py` | `app/main.py` |
|---|---|---|
| Entrypoint Docker | **Sí** (`uvicorn server:app`) | No |
| Entrypoint README | No | **Sí** (`uvicorn app.main:app`) |
| Prefijo API | `/api/*` | `/api/v1/*` |
| Routers montados | `auth`, `backtest`, `paper_trading` | `auth`, `backtest`, `paper_trading`, `market`, `screener`, `llm` |
| CORS | `["*"]` + `allow_credentials=True` | Lista explícita (`localhost:3000`, `localhost:5173`) |
| Lógica de negocio | Incluida inline (~1400 líneas) | Delegada a módulos en `app/` |
| Background tasks | `background_sector_sync`, `background_scanner` | No definidos |
| Redis | Conectado y usado | No inicializado en este entrypoint |
| Configuración | `os.getenv()` directo | `pydantic-settings` |
| Modelos ML | Importados y usados en scoring | No referenciados directamente |

**Conclusión:** `server.py` es la aplicación real en producción (Docker), mientras que `app/main.py` es un esqueleto modular parcialmente implementado. La divergencia es significativa y requiere resolución inmediata.

## 5.2 Endpoints duplicados o divergentes

- `/api/auth/*` (server.py) vs `/api/v1/auth/*` (app/main.py)
- `/api/backtest/*` (server.py) vs `/api/v1/backtest/*` (app/main.py)
- `/api/paper/*` (server.py) vs `/api/v1/paper/*` (app/main.py)

Los endpoints en `app/main.py` para `market`, `screener` y `llm` no existen en `server.py`.

## 5.3 Módulos mock/stub

Los siguientes endpoints en `app/api/endpoints/` devuelven datos mock/hardcodeados:

- [market.py:L27-L48](file:///Users/raymondpalacios/Documents/Bootcamp%20Data%20Science/Iosef_Finance/backend/app/api/endpoints/market.py#L27-L48): `/api/v1/market/overview` retorna datos ficticios
- [screener.py:L21-L86](file:///Users/raymondpalacios/Documents/Bootcamp%20Data%20Science/Iosef_Finance/backend/app/api/endpoints/screener.py#L21-L86): `/api/v1/screener` retorna tickers hardcodeados

Estos endpoints no deben exponerse en producción sin datos reales.

## 5.4 Configuraciones no alineadas

| Configuración | `security.py` | `config.py` |
|---|---|---|
| Nombre de variable | `JWT_SECRET_KEY` | `SECRET_KEY` |
| Valor por defecto | `"09d25e094faa..."` (hardcodeado) | `"change_me_to_a_secure_random_key_in_production"` |
| TTL del token | 7 días | 8 días |

Dos fuentes de verdad para secretos y TTL de token es una receta para inconsistencias.

## 5.5 Riesgos por migración incompleta

- El README referencia `frontend/` y `realtime/` que no existen; el frontend real está en `frontend-v2/`
- La instrucción de arranque del README (`fastapi dev app/main.py`) no refleja el entrypoint real de Docker
- `app/main.py` monta routers que `server.py` no monta, y viceversa
- La función `compute_ml_score()` usa el modelo sintético sin advertencia ni flag de validación
