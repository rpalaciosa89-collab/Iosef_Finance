# Sprint 10 Planning: Premium UX, Auth UI & Business Model
**Framework:** Scrum Ágil
**Product Owner & Scrum Master:** Raymond
**Equipo:** Javier (Dev), Luis (QA/Sec), Carlos (Quant), **Rosaura (UX/Business Strategy)**

---

## 1. Integración de Rosaura (UX y Estrategia)
A partir de este Sprint, Rosaura se une al equipo directivo. Como Scrum Master, sus objetivos primordiales bajo mi mando son:
1. **Premium UX/UI:** Asegurar que Iosef Finance ofrezca una experiencia visual de lujo que justifique el dinero del usuario.
2. **Modelo de Negocio:** Investigar el mercado institucional y diseñar los *tiers* de monetización.
3. **Estrategia de Lanzamiento:** Comenzar a planificar el "Go-To-Market" ahora que tenemos Backend, Seguridad y un Core Cuantitativo.

---

## 2. Levantamiento de Requerimientos Estructurado (Rol: Product Owner - Raymond)
Para este sprint, el enfoque es *Experiencia Institucional y Cierre de Flujos Visuales*:

### Epic 1: Interfaz de Seguridad Institucional (Login UI)
*   **User Story 1.1:** *Como inversor, quiero ver una pantalla de Login lujosa y corporativa al abrir Iosef Finance, que inspire confianza inmediata.*
*   **User Story 1.2:** *Como sistema, el frontend debe proteger las rutas de React y exigir el token JWT para ver el Dashboard.*

### Epic 2: Visualizador Cuantitativo (Backtesting UI)
*   **User Story 2.1:** *Como analista financiero, quiero visualizar el Total Return, Max Drawdown y Sharpe Ratio en un panel lateral limpio al seleccionar una acción.*

### Epic 3: Fundamentos del Modelo de Negocio
*   **User Story 3.1:** *Como CEO, quiero un informe del modelo de negocio (Tiers de precios, perfil de cliente ideal) para preparar la monetización de la plataforma.*

---

## 3. Plan Táctico para el Sprint 10 (Scrum Master - Raymond)

### Tarea A: Arquitectura Frontend y Login Premium (Javier & Rosaura)
*   **Rosaura:** Diseñará los lineamientos estéticos del Login (colores oscuros, *glassmorphism*, tipografía premium).
*   **Javier:** Codificará el componente `<Login />` en React/Vite, implementará React Router (`/login` y `/dashboard`) y conectará la API de Auth (`/api/auth/token`).

### Tarea B: UI de Backtesting Cuantitativo (Javier & Carlos)
*   **Carlos:** Validará qué métricas tienen más peso visual para un fondo de inversión.
*   **Javier:** Creará un componente `<BacktestPanel />` en el dashboard que consulte la API y formatee el PnL y el Sharpe Ratio.

### Tarea C: Estrategia de Monetización (Rosaura)
*   **Rosaura:** Redactará el documento oficial de Estrategia de Marketing y Modelo de Negocio (`docs/estrategia_negocio.md`), definiendo cómo Iosef Finance entregará más valor por el dinero pagado.

### Tarea D: Auditoría de Seguridad Frontend (Luis)
*   **Luis:** Evaluará el almacenamiento del JWT en el frontend para evitar ataques XSS y validará las redirecciones de seguridad.

---
> [!NOTE]
> **Gestión Documental (Cumplimiento de la orden del Usuario):**
> A partir de ahora, cada plan de Sprint se guardará históricamente en el directorio `/docs/sprints/` bajo una nomenclatura estandarizada (Ej: `Sprint_10_UX_Auth.md`).

> [!IMPORTANT]
> **Aprobación del Stakeholder:**
> Rosaura ha sido integrada exitosamente al ecosistema y tiene su perfil completo definido. La documentación histórica está en marcha.
> ¿Das tu aprobación para arrancar el **Sprint 10** y ejecutar este plan estructurado?
