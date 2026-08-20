# 1. Matriz Completa de Hallazgos

**Total: 20 hallazgos** (3 Críticos, 5 Altos, 7 Medios, 5 Bajos)

---

| ID | Severidad | Categoría | Título | Prioridad | Esfuerzo |
|---|---|---|---|---|---|
| H-001 | Crítica | Arquitectura | Deriva arquitectónica — Dos backends divergentes | Inmediata | Medio |
| H-002 | Crítica | Seguridad | JWT secret hardcodeado con fallback inseguro | Inmediata | Bajo |
| H-003 | Crítica | ML | Modelo XGBoost entrenado con datos sintéticos | Inmediata | Alto |
| H-004 | Alta | Seguridad | CORS `*` con `allow_credentials=True` | Próximo sprint | Bajo |
| H-005 | Alta | DevOps | Ausencia total de CI/CD | Próximo sprint | Medio |
| H-006 | Alta | Frontend | URLs hardcodeadas en frontend (sin variables de entorno) | Próximo sprint | Medio |
| H-007 | Alta | Testing | Sin tests de frontend | Próximo sprint | Medio |
| H-008 | Alta | Seguridad | Token JWT en localStorage (vulnerable a XSS) | Próximo sprint | Medio |
| H-009 | Media | Testing | Sin tests de integración HTTP | Próximo sprint | Medio |
| H-010 | Media | Seguridad | Inconsistencia de configuración JWT entre `security.py` y `config.py` | Próximo sprint | Bajo |
| H-011 | Media | Frontend | Bug de contrato en Analytics (URL mal formada) | Próximo sprint | Bajo |
| H-012 | Media | Frontend/Backend | Posible desalineación de contrato Signal Lab | Próximo sprint | Bajo |
| H-013 | Media | Backend | WebSocket declarado pero no implementado | Backlog | Medio |
| H-014 | Media | Performance | Operaciones bloqueantes en endpoints síncronos | Backlog | Medio |
| H-015 | Media | Datos | Doble persistencia SQLite (SQLAlchemy + sqlite3 directo) | Backlog | Alto |
| H-016 | Baja | Documentación | README desactualizado — Módulos inexistentes | Backlog | Bajo |
| H-017 | Baja | Configuración | Archivos .db en raíz del backend sin protección en .gitignore | Backlog | Bajo |
| H-018 | Baja | Frontend | Estilos inline y tipos `any` en frontend | Backlog | Medio |
| H-019 | Baja | DevOps | Sin healthchecks en Docker Compose | Backlog | Bajo |
| H-020 | Media | DevOps | Sin variables de entorno en docker-compose | Próximo sprint | Bajo |

---

## Distribución por Severidad

| Severidad | Cantidad | % |
|---|---|---|
| Crítica | 3 | 15% |
| Alta | 5 | 25% |
| Media | 7 | 35% |
| Baja | 5 | 25% |

## Distribución por Categoría

| Categoría | Cantidad |
|---|---|
| Seguridad | 4 |
| Frontend | 4 |
| DevOps | 3 |
| Testing | 3 |
| Arquitectura | 1 |
| ML | 1 |
| Backend | 1 |
| Performance | 1 |
| Datos | 1 |
| Documentación | 1 |
| Configuración | 1 |
| Frontend/Backend | 1 |

## Distribución por Prioridad

| Prioridad | Cantidad | Esfuerzo acumulado |
|---|---|---|
| Inmediata | 3 | Bajo + Medio + Alto |
| Próximo sprint | 9 | 4 Bajo + 5 Medio |
| Backlog | 8 | 3 Bajo + 3 Medio + 2 Alto |
