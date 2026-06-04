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
