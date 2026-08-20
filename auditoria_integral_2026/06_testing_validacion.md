# 7. Testing y Validación

---

## 7.1 Qué existe

| Categoría | Cantidad | Archivos |
|---|---|---|
| Tests unitarios backend | 33 | `test_scoring.py` (12), `test_signal_evaluation.py` (21) |
| ESLint frontend | Configurado | `eslint.config.js` |
| Herramientas declaradas | mypy, black, isort | `pyproject.toml` |
| Scripts de test/debug | ~13 | `test_scan_debug.py`, `test_exec.py`, etc. |

**Resultado actual:** 33/33 tests pasan. Suite pequeña pero sólida en lo que cubre.

## 7.2 Qué falta

| Categoría | Estado |
|---|---|
| Tests de integración HTTP (API) | **Inexistente** |
| Tests de frontend (componentes, hooks, páginas) | **Inexistente** |
| Tests end-to-end (E2E) | **Inexistente** |
| Tests de carga/performance | **Inexistente** |
| Tests de seguridad (SAST, DAST) | **Inexistente** |
| Type checking automatizado (mypy) | **No ejecutado en pipeline** |
| Formateo automatizado (black, isort) | **No ejecutado en pipeline** |
| Cobertura de código | **No medida** |

## 7.3 Qué debería probarse primero

1. **Auth flow:** Registro → Login → Token → Protected endpoint → 401 en token expirado
2. **Paper trading:** Crear cuenta → Execute trade → Refresh portfolio → Close trade
3. **Screener:** Request scan → Validar estructura de respuesta → Validar scores en rango
4. **Frontend AuthContext:** Login → setToken → isAuthenticated → Logout → clearToken
5. **Frontend ProtectedRoute:** Sin token → redirige a /login. Con token → renderiza children

## 7.4 Qué pruebas automatizadas aportarían más valor

| Prioridad | Tipo | Impacto |
|---|---|---|
| P1 | Tests de integración HTTP para auth | Evita regresiones en el flujo más crítico |
| P1 | Tests de integración HTTP para paper trading | Valida el core de negocio |
| P2 | Tests unitarios de frontend (AuthContext, ProtectedRoute) | Previene bugs de sesión |
| P2 | Tests de contrato API (validación de schemas de respuesta) | Detecta breaking changes |
| P3 | Tests E2E con Playwright (login → dashboard → screener) | Valida la experiencia completa |
| P3 | Tests de carga con k6 o locust | Identifica cuellos de botella |
