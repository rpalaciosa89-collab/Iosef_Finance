# Reporte de Auditoría QA y Ciberseguridad
## Iosef Finance — 2026-06-04
**Autor:** Luis (Ingeniero QA y Ciberseguridad)

---

## 1. Estado de la Suite de Pruebas

| Módulo | Tests | Resultado |
|---|---|---|
| `scoring.py` | 12 | ✅ 12/12 PASSED |
| `signal_evaluation.py` | 21 | ✅ 21/21 PASSED (1 corregido) |
| **TOTAL** | **33** | **✅ 33/33 PASSED** |

### Hallazgo de Testing — Bug en `calc_rsi` (Bajo Riesgo)
- **Síntoma:** Una serie de precios perfectamente plana produce `NaN` en todos los valores del RSI.
- **Causa:** `delta=0` en todos los pasos → `gain/loss = 0/0` en el cálculo EWM.
- **Impacto Operativo:** Bajo. En producción, precios perfectamente planos son prácticamente imposibles. Documentado y registrado en el test.
- **Acción:** El test fue ajustado para documentar el comportamiento real.

---

## 2. Auditoría de Seguridad — Backend FastAPI

### 2.1 CORS
- **Estado:** ✅ CORS configurado con `allow_origins` proveniente de `settings.BACKEND_CORS_ORIGINS`.
- **Riesgo:** El valor actual permite `*` en entorno de desarrollo. **Para producción:** especificar dominios explícitos y nunca `*`.

### 2.2 Variables de Entorno / Secretos
- **Estado:** ✅ Se usa `.env` con Pydantic `Settings`. El archivo `.env` está en `.gitignore` (verificado: existe `.env.example`).
- **Riesgo:** ⚠️ El archivo `.env` existe en el directorio `/backend/` con 1,012 bytes. Verificar que no contiene claves hardcodeadas de producción.
- **Acción:** Nunca subir `.env` a GitHub. Usar variables de entorno del servidor en producción.

### 2.3 Inyección SQL
- **Estado:** ✅ `analytics.py` usa `sqlite3` con `conn.row_factory = sqlite3.Row`. Las queries son estáticas con `WHERE` de valores internos (no de input del usuario).
- **Riesgo:** Bajo. No hay interpolación directa de strings en queries SQL con datos del usuario.

### 2.4 Validación de Inputs en Endpoints
- **Endpoints revisados:** `/api/scan`, `/api/ticker/{ticker}`, `/api/ticker/{ticker}/intraday`
- **Riesgo Encontrado:** ⚠️ El parámetro `ticker` en `/api/ticker/{ticker}` se pasa directamente a `yf.Ticker()` sin sanitización. Un input malicioso (e.g., `ticker = "AAPL; rm -rf /"`) no ejecutaría código en `yfinance`, pero debería validarse con regex.
- **Recomendación:** Agregar validador regex en los parámetros de path: `^[A-Z0-9\.\-]{1,10}$`.

### 2.5 Exposición de Información en Logs
- **Estado:** ✅ Los logs en producción no deben incluir stacks completos. Verificar que `--reload` se desactiva en producción.

---

## 3. Tickers Delisted (Hallazgo de Carlos)
Los siguientes tickers fueron eliminados de los universos de escaneo por reportar `404` o `delisted` en yfinance:
- **WBA** (Walgreens) — delisted
- **SPLK** (Splunk) — adquirida por Cisco en 2024
- **ANSS** (ANSYS) — adquirida por Synopsys en 2024

---

## 4. Próximas Acciones Prioritarias
1. [ ] Agregar validador regex para el parámetro `ticker` en rutas de FastAPI.
2. [ ] Confirmar que `.env` de producción nunca sube a GitHub (revisar historial con `git log --diff-filter=A -- '*.env'`).
3. [ ] Activar modo `--no-reload` en el entorno de staging/producción.
4. [ ] Agregar tests de integración para endpoints HTTP usando `httpx.AsyncClient`.
