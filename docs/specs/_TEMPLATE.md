# Plantilla de Spec — Iosef Finance

> Toda nueva modificación debe usar esta plantilla. Una Spec es un contrato: si el
> código cumple los criterios de aceptación, el ítem está terminado. Se escribe
> ANTES de codificar (Spec-Driven Development) y se cierra con un bucle de
> verificación (Loop Engineering).

---

## SP-<Ola>.<item> — <Título corto>

- **Ola:** <número>
- **Prioridad:** Crítica / Alta / Media / Baja
- **Esfuerzo:** Bajo / Medio / Alto (~horas)
- **Hallazgo/auditoría:** <ID o evidencia observada (fecha, log, archivo:línea)>

### 1. Contexto y problema (medible)

<Descripción del problema con dato objetivo: log de error, métrica, comportamiento observado.>

### 2. Root cause

<Causa raíz con referencia a archivo:línea si existe.>

### 3. Comportamiento (Given / When / Then)

- **GIVEN** <estado inicial>
- **WHEN** <acción del usuario/sistema>
- **THEN** <resultado observable por API, UI o DB>

### 4. Criterios de aceptación

1. <criterio medible 1>
2. <criterio medible 2>
3. ...

### 5. Tests a escribir primero (TDD)

- `backend/tests/test_<modulo>.py::test_<caso>`
- ...

### 6. Implementación

<Orientación técnica: archivos, módulos, enfoque. No pseudocódigo final.>

### 7. Verificación

```bash
<comandos exactos>
```

### 8. Definition of Done (cierre de bucle)

- [ ] Tests en verde
- [ ] Métrica de la Ola cumplida (ver plan maest ..........§1.3)
- [ ] Commit atómico `[Ola<X>.<Y>] <título>`
- [ ] CHANGELOG de la ola actualizado con resultado + métrica