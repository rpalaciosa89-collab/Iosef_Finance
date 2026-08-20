# 🏛️ IOSEF FINANCE TERMINAL — MANUAL DE ARRANQUE COMPLETO

> **Versión:** Sprint 12.2 — Junio 2026  
> **Equipo:** Raymond (PM), Carlos (Quant/ML), Rosaura (UX/Estrategia)  
> **Documento oficial de arranque del proyecto**

---

## 🔐 CREDENCIALES DE ACCESO

| Campo         | Valor                    |
|---------------|--------------------------|
| **Email**     | `admin@iosef.finance`    |
| **Contraseña**| `admin123`               |
| **URL Login** | http://localhost:5173/login |

> ⚠️ Estas credenciales son para el entorno de desarrollo local. Cámbialas antes de cualquier despliegue en producción.

---

## 🏗️ ARQUITECTURA DEL SISTEMA

```
Iosef_Finance/
├── backend/          ← API FastAPI + Motor ML (Puerto 8002)
│   ├── server.py     ← Servidor principal + scan loop + paper trading
│   ├── app/
│   │   ├── api/      ← Rutas: auth, backtest, paper_trading
│   │   ├── services/ ← Motor ML, scoring, LSTM, analytics
│   │   ├── models/   ← Modelos SQLAlchemy (users, paper_trading)
│   │   ├── schemas/  ← Pydantic schemas
│   │   ├── core/     ← Seguridad, JWT, hashing
│   │   └── db/       ← Conexión SQLite (iosef_finance.db)
│   ├── config/       ← TITAN_100 universe
│   ├── models/       ← Modelos XGBoost + LSTM entrenados (.pkl/.h5)
│   └── iosef_finance.db  ← Base de datos SQLite (usuarios, paper trading)
│
├── frontend-v2/      ← App React + Vite (Puerto 5173)
│   └── src/
│       ├── pages/    ← Login.tsx
│       ├── tabs/     ← Screener, Analytics, SignalLab, PaperTrading
│       ├── context/  ← AuthContext (JWT token)
│       └── components/ ← ActionableConclusions, TickerCard, etc.
│
├── data/             ← Históricos de precios y tickers
├── snapshots/        ← latest.json (caché del scan actual)
├── docker-compose.yml ← Despliegue productivo completo
└── docs/             ← Documentación del proyecto
    └── MANUAL_ARRANQUE.md  ← 📌 ESTE ARCHIVO
```

### Servicios y Puertos

| Servicio         | Puerto | Descripción                                      |
|------------------|--------|--------------------------------------------------|
| **Frontend**     | `5173` | App React (Vite dev server)                      |
| **Backend API**  | `8002` | FastAPI + motor ML + paper trading               |
| **Redis**        | `6379` | Caché en memoria (scan data, señales, lifecycle) |
| ~~Port 8000~~    | `8000` | Instancia legacy (no usar, puede coexistir)      |

---

## 🚀 ARRANQUE DEL PROYECTO (Modo Desarrollo)

> **Este es el procedimiento oficial.** Sigue el orden exacto.

### Requisitos Previos

```bash
# Verificar versiones
python3 --version    # Python 3.12+
node --version       # Node.js 18+
redis-cli ping       # Debe responder: PONG
```

Si Redis no responde: `brew services start redis`

---

### PASO 1 — Iniciar Redis (si no está corriendo)

```bash
brew services start redis
# Verificar:
redis-cli ping   # → PONG
```

---

### PASO 2 — Iniciar el Backend (Puerto 8002)

```bash
# Desde la raíz del proyecto:
cd backend
source ../venv/bin/activate

# Iniciar servidor principal (paper trading + ML engine + scan loop):
uvicorn server:app --host 0.0.0.0 --port 8002 --reload
```

✅ El backend está listo cuando ves:
```
INFO:     Uvicorn running on http://0.0.0.0:8002
INFO: [SCAN] Starting background scan loop...
```

---

### PASO 3 — Iniciar el Frontend (Puerto 5173)

```bash
# Nueva terminal — desde la raíz del proyecto:
cd frontend-v2
npm run dev
```

✅ El frontend está listo cuando ves:
```
VITE ready in XXXms
➜ Local: http://localhost:5173/
```

---

### PASO 4 — Acceder al Terminal

1. Abre el navegador en: **http://localhost:5173/login**
2. Ingresa con las credenciales:
   - Email: `admin@iosef.finance`
   - Contraseña: `admin123`
3. Serás redirigido al **Dashboard principal**.

---

## 🐳 ARRANQUE ALTERNATIVO — Docker (Producción)

Para levantar todo el sistema como un único stack:

```bash
# Desde la raíz del proyecto:
docker-compose up --build

# En background:
docker-compose up -d --build
```

| Servicio    | URL Accesible                |
|-------------|------------------------------|
| Frontend    | http://localhost:80           |
| Backend API | http://localhost:8002         |
| Redis       | localhost:6379               |

Para detener todo:
```bash
docker-compose down
```

---

## 🧠 MÓDULOS DEL TERMINAL

### 📊 Screener (TITAN 100)
- Muestra las **98 acciones del universo TITAN 100** actualizadas cada 60 segundos.
- Divide la tabla en dos grupos:
  - **🏆 Premium** (P(WIN) ≥ 70% o ≤ 30%): Señales de alta certidumbre.
  - **📋 Resto del Mercado**: El resto del universo para monitoreo.
- Cada ticker muestra: Precio, CHG%, RSI, Vol Relativo, Momentum 1M, Score (0-9), P(WIN), Señal.

### 🔬 Signal Lab
- Análisis detallado por ticker: gráfica de precios, indicadores técnicos, salida del modelo ML.

### 📈 Analytics
- Métricas de portfolio, backtesting histórico y estadísticas del modelo.

### 💼 Paper Trading
- Simulación de operaciones con $100,000 virtuales.
- El motor ejecuta trades automáticamente solo cuando **P(WIN) ≥ 70%** (LONG) o **≤ 30%** (SHORT).
- Historial limpio desde el sprint 12.2.

### ⚡ TITAN 100
- Vista del universo completo de activos monitoreados.

---

## 🔧 COMANDOS DE MANTENIMIENTO

### Verificar servicios activos
```bash
# ¿Están corriendo?
lsof -i :8002   # Backend
lsof -i :5173   # Frontend
lsof -i :6379   # Redis
```

### Forzar re-escaneo del mercado
```bash
curl -X POST http://localhost:8002/api/scan/refresh
```

### Limpiar caché de Redis (señales)
```bash
redis-cli FLUSHDB
```

### Limpiar lifecycle de tickers (trades automáticos)
```bash
redis-cli KEYS "lifecycle:*" | xargs redis-cli DEL
```

### Reiniciar Paper Trading (cuenta a $100,000)
```bash
cd backend
sqlite3 iosef_finance.db "DELETE FROM paper_trades; DELETE FROM paper_positions; UPDATE paper_accounts SET cash_balance = 100000;"
redis-cli KEYS "lifecycle:*" | xargs redis-cli DEL
```

### Cambiar contraseña del admin
```bash
cd backend
# Editar update_pwd.py con la nueva contraseña y ejecutar:
../venv/bin/python3 update_pwd.py
```

---

## 🗄️ BASE DE DATOS

**Archivo:** `backend/iosef_finance.db` (SQLite)

| Tabla              | Descripción                                   |
|--------------------|-----------------------------------------------|
| `users`            | Cuentas de usuario con hashed_password (bcrypt)|
| `paper_accounts`   | Cuenta virtual de simulación ($100,000 inicial)|
| `paper_positions`  | Posiciones abiertas actualmente               |
| `paper_trades`     | Historial completo de operaciones             |

### Inspeccionar directamente
```bash
sqlite3 backend/iosef_finance.db ".tables"
sqlite3 backend/iosef_finance.db "SELECT * FROM paper_accounts;"
sqlite3 backend/iosef_finance.db "SELECT * FROM users;"
```

---

## 🤖 MOTOR ML — TITAN 100

### Modelo
- **XGBoost** + **LSTM Global** entrenados sobre el universo TITAN 100.
- Genera una puntuación **P(WIN)**: probabilidad de ganancia en la próxima vela.
- **Score 0-9**: índice compuesto de calidad de señal.

### Regla de Ejecución Auto-Trading
```
IF P(WIN) >= 70%  → LONG  (alta probabilidad de subida)
IF P(WIN) <= 30%  → SHORT (alta probabilidad de bajada)
ELSE              → Sin operación (zona gris, no se arriesga capital)
```

### Universo TITAN 100
Definido en `backend/config/titan_universe.py`. Incluye las 98 acciones institucionales de alta liquidez distribuidas en sectores: Technology, Healthcare, Industrials, Energy, Consumer, Financial Services y más.

---

## 📡 ENDPOINTS DE LA API

Base URL: `http://localhost:8002`

| Método | Ruta                               | Descripción                                 |
|--------|------------------------------------|---------------------------------------------|
| GET    | `/`                                | Health check del servidor                   |
| POST   | `/api/auth/token`                  | Login → JWT token                           |
| POST   | `/api/auth/register`               | Registro de nuevo usuario                   |
| GET    | `/api/scan`                        | Datos del screener (todos los tickers)      |
| POST   | `/api/scan/refresh`                | Forzar re-escaneo inmediato                 |
| GET    | `/api/ticker/{symbol}`             | Datos de un ticker específico               |
| GET    | `/api/paper-trading/portfolio`     | Cartera virtual completa                    |
| POST   | `/api/paper-trading/account`       | Crear cuenta de simulación                  |
| POST   | `/api/paper-trading/execute`       | Ejecutar operación simulada                 |
| POST   | `/api/paper-trading/close/{id}`    | Cerrar posición                             |
| POST   | `/api/paper-trading/refresh`       | Mark-to-market (actualizar precios)         |
| GET    | `/docs`                            | Swagger UI (documentación interactiva)      |

---

## 🗂️ DOCUMENTACIÓN ADICIONAL

| Archivo                              | Contenido                                         |
|--------------------------------------|---------------------------------------------------|
| `docs/aprendizajes.md`               | Lecciones técnicas del equipo                     |
| `docs/estrategia_negocio.md`         | Visión de producto y estrategia                   |
| `docs/mejores_practicas.md`          | Guía de código y calidad                          |
| `docs/gestion_cambios.md`            | Control de cambios y versiones                    |
| `docs/auditoria_cuantitativa_carlos.md` | Auditoría del modelo ML (Carlos)               |
| `docs/sprints/`                      | Notas técnicas por sprint                         |
| `agents/system_prompts_equipo.md`    | Definición de personas del equipo (Carlos/Rosaura)|

---

## 🛑 SOLUCIÓN DE PROBLEMAS FRECUENTES

### ❌ "Credenciales inválidas" al hacer login
```bash
# Resetear contraseña del admin:
cd backend
../venv/bin/python3 update_pwd.py
# (asegúrate de que el script tiene la contraseña correcta)
```

### ❌ El screener muestra menos de 98 tickers
```bash
# Forzar re-escaneo:
curl -X POST http://localhost:8002/api/scan/refresh
# Limpiar caché de Redis:
redis-cli FLUSHDB
```

### ❌ "No such table: paper_accounts"
El backend está apuntando a la `app.db` vacía en lugar de `iosef_finance.db`. Verifica que el proceso corre desde `backend/` como directorio de trabajo.

### ❌ Redis connection refused
```bash
brew services start redis
# o:
redis-server --daemonize yes
```

### ❌ Paper Trading muestra datos basura (ANET/SYK)
```bash
cd backend
sqlite3 iosef_finance.db "DELETE FROM paper_trades; DELETE FROM paper_positions; UPDATE paper_accounts SET cash_balance = 100000;"
redis-cli KEYS "lifecycle:*" | xargs redis-cli DEL
```

---

## 📝 HISTORIAL DE VERSIONES

| Sprint   | Fecha     | Cambio Principal                                      |
|----------|-----------|-------------------------------------------------------|
| Sprint 1-9 | May 2026 | Fundación del proyecto, screener básico, ML inicial  |
| Sprint 10  | Jun 2026 | Sistema de autenticación JWT, login institucional    |
| Sprint 11  | Jun 2026 | Paper Trading engine, auto-trading ML                |
| Sprint 12.1| Jun 2026 | Fix 98/98 tickers, scrollbar, grupos Premium/Resto   |
| Sprint 12.2| Jun 2026 | Purga de trades basura, filtro estricto ≥70%/≤30%   |

---

*Documento generado por el equipo Iosef Finance — Sprint 12.2*  
*Última actualización: 5 de Junio, 2026*
