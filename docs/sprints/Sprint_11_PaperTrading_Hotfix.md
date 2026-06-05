# Sprint 11 Planning: Paper Trading Engine & Corrección de Errores
**Framework:** Scrum Ágil
**Product Owner & Scrum Master:** Raymond
**Equipo:** Javier (Dev), Luis (QA/Sec), Carlos (Quant), Rosaura (UX/Strategy)

---

## 1. Retrospectiva Inmediata (Incidente en Producción)
El Stakeholder reportó un fallo al ejecutar el backtest para el ticker **SYK** (`Error ejecutando el backtest en el backend`). 
*   **Análisis inicial (Luis - QA/Sec):** Los logs del servidor revelaron un `401 Unauthorized` en el endpoint `GET /api/backtest/SYK`. Esto indica que el Token JWT no fue aceptado, expiró repentinamente, o la petición `OPTIONS` (CORS) bloqueó el flujo del token.
*   **Acción Correctiva:** Javier y Luis deberán depurar el flujo de autenticación en las peticiones y los middlewares para asegurar que el token persista y se envíe correctamente en cada click.

---

## 2. Levantamiento de Requerimientos (Rol: Product Owner - Raymond)
El objetivo central de este sprint es el **Paper Trading Institucional**. Queremos simular la realidad del mercado (que abre mañana) para medir cómo se comportarían las carteras de nuestros clientes basándose en nuestras señales predictivas.

### Epic 1: Infraestructura de Paper Trading
*   **User Story 1.1:** *Como sistema, quiero tener un motor de Cuentas Simuladas que comience con un balance virtual (Ej: $100,000 USD).*
*   **User Story 1.2:** *Como inversor, quiero poder "ejecutar" (simular) una operación de compra/venta cuando el modelo de Iosef Finance emita una señal fuerte, bloqueando capital virtual.*

### Epic 2: Seguimiento de Señales en Tiempo Real
*   **User Story 2.1:** *Como analista cuantitativo, quiero que el sistema escuche las señales de nuestro algoritmo (Cruce de Medias / LSTM / XGBoost) e inserte automáticamente las posiciones en la cuenta simulada (o provea la alerta exacta al cliente).*

---

## 3. Plan Táctico para el Sprint 11 (Scrum Master - Raymond)

### Tarea A: Hotfix del Backtester (SYK / 401 Unauthorized) (Javier & Luis)
*   **Luis:** Reproducirá el error con SYK y auditará el paso del Token Bearer desde el frontend al backend.
*   **Javier:** Implementará el parche en `TickerModal.tsx` o en `server.py` (CORS/Auth Dependency) para evitar el `401 Unauthorized`.

### Tarea B: Motor de Cuentas Simuladas (Javier & Carlos)
*   **Javier:** Diseñará los modelos de base de datos `PaperAccount` y `PaperTrade` (usando SQLAlchemy en `backend/app/models/`).
*   **Javier:** Creará los endpoints `/api/paper-trading/execute` y `/api/paper-trading/portfolio`.
*   **Carlos:** Validará que la lógica de descuento de balance y cálculo de PnL en tiempo real (Mark-to-Market) sea financieramente precisa.

### Tarea C: Interfaz UI de Paper Trading (Rosaura & Javier)
*   **Rosaura:** Diseñará una nueva pestaña o sección "Portfolio Simulation" en el Dashboard, manteniendo la estética *Premium*.
*   **Javier:** Conectará el frontend con el nuevo motor de Paper Trading.

---
> [!IMPORTANT]
> **Aprobación del Stakeholder:**
> Hemos registrado el error de SYK y estructurado el motor de Paper Trading como solicitaste, listos para correr mañana cuando abra el mercado. 
> ¿Das tu aprobación para iniciar el **Sprint 11** y proceder con las correcciones y la construcción de la simulación?
