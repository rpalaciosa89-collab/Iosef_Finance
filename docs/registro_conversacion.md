# Registro de Conversaciones y Decisiones Arquitectónicas

## 2026-06-04: Inicialización y Problemas de Puertos
- **Incidente:** El usuario reportó problemas para levantar el backend en el puerto `8000` (puerto ocupado).
- **Acción:** Se migró temporalmente el backend a `8001` y se ajustó el frontend (`index.html`) para apuntar a `8001/api/v1`. 
- **Reversión:** Debido a que este cambio rompió la visibilidad de los datos para el usuario, se hizo un rollback completo. Se restauró el frontend a `8000/api` y se restauró el backend a su estado puro. 
- **Descubrimiento:** Se levantó el microservicio de Go (Realtime) en el puerto `8080` (el cual depende de Redis en `6379`).

## 2026-06-04: Formalización del Equipo (Agentes)
- Se definieron y documentaron (en `agents/system_prompts_equipo.md`) los 4 perfiles clave:
  1. **Raymond:** Supervisor y PM.
  2. **Javier:** Infraestructura y Desarrollo Senior.
  3. **Luis:** Ciberseguridad y QA.
  4. **Carlos:** Ing. Financiero, Ciencia de Datos y Machine Learning.
- **Directriz de Presidencia (Usuario):** "Quiero matemática pero con precisión de francotirador, estadística aplicada pura, no quiero poesía, quiero realismo. Estructura, mejora continua y excelencia (nivel Bill Gates/Elon Musk)."

## 2026-06-04: Plan de Auditoría
- Se aprobó el *Plan de Auditoría Estricta y Mejora Continua* (Fases 1 a 4).
- Se exigió la creación inmediata de la estructura documental (este directorio `docs/`).

## 2026-06-04: Resolución de Incidencia (Pantalla Negra en Frontend)
- **Incidente:** Al hacer clic en una fila del *Screener Table*, el modal del ticker mostraba una pantalla negra irrecuperable.
- **Diagnóstico (Raymond):** Se identificó un `TypeError` en React. El backend (FastAPI) no estaba serializando los objetos `trade_plan` y `trade_tracking` para los activos sin señales vigentes. Al recibir `undefined`, las funciones `.toFixed()` en `TickerModal.tsx` causaban un fallo en todo el árbol de componentes de React.
- **Acción:**
  - Se modificó `server.py` para devolver siempre un esquema base (`null-safe`) incluso sin señales.
  - Se añadió programación defensiva en `TickerModal.tsx` asignando valores por defecto (`ticker.trade_plan ?? { ... }`).
  - Se creó un `<ErrorBoundary>` global para el modal, evitando futuros fallos silenciosos.

## 2026-06-04: Pivot Estratégico (Core Predictivo)
- **Directiva del Usuario:** Iosef Finance **NO** es una plataforma de ejecución de órdenes ni broker. Su único propósito es la **Predicción del Mercado** en tiempo real mediante estadística pura, Machine Learning y Redes Neuronales.
- **Acción:** Se descarta la integración con Alpaca/Brokers. El Sprint 2 se dedicará al 100% en sustituir las reglas estáticas por un Motor Predictivo (XGBoost / Redes Neuronales) que calcule probabilidades de éxito de las señales basándose en datos intradiarios y diarios.
