# Ola 5 — Auth Robusta — CHANGELOG

**Fecha:** 2026-06-10
**Ejecutor:** Auditor Integral de Plataforma Financiera (Agente)
**Duración real:** ~3 horas
**Duración estimada:** ~6 horas

---

## Resumen

Auth endurecida con cookies HttpOnly, rate limiting, blacklist de logout, endpoints nuevos, y frontend migrado de localStorage a cookies.

## Hallazgos Resueltos

| ID | Severidad | Descripción | Estado |
|---|---|---|---|
| H-003 | Alta | Token JWT en localStorage (XSS vulnerable) | ✅ Resuelto |
| H-015 | Alta | Sin rate limiting en auth | ✅ Resuelto |
| H-018 | Media | Sin endpoint de logout | ✅ Resuelto |
| H-021 | Baja | TTL de JWT 7 días | ✅ Resuelto |

## Cambios

### Backend — Auth endurecida

**`app/config.py`**
- `ACCESS_TOKEN_EXPIRE_MINUTES`: 7 días → **24 horas**
- Nuevas configs: `JWT_COOKIE_NAME`, `JWT_COOKIE_SECURE`, `AUTH_RATE_LIMIT_REQUESTS=10`, `AUTH_RATE_LIMIT_WINDOW=60s`

**`app/api/auth.py`** (reescrito)
- Login ahora devuelve JWT en **cookie HttpOnly** + sigue devolviendo token en JSON (backward compat)
- Rate limiting en register y login (10 req/min por IP, vía Redis)
- Nuevo endpoint `GET /api/auth/me` → datos del usuario autenticado
- Nuevo endpoint `GET /api/auth/status` → `{authenticated, email}` (para frontend)
- Nuevo endpoint `POST /api/auth/logout` → blacklist del token + delete cookie

**`app/core/deps.py`** (reescrito)
- Sub-dependencia `_resolve_token`: prueba Bearer header primero, fallback a cookie HttpOnly
- `get_current_user` simplificado: recibe token resuelto + validación + blacklist check
- `_is_blacklisted`: verifica Redis por JWT en lista negra

### Frontend — Migración a cookies

**`src/context/AuthContext.tsx`** (reescrito)
- Sin localStorage. Estado verificado via `GET /api/auth/status` con `credentials: 'include'`
- Nuevos estados: `isLoading`, `userEmail`
- Login: solo cambia estado (cookie ya viene del servidor)
- Logout: llama `POST /api/auth/logout` + limpia estado local

**`src/lib/api.ts`** (actualizado)
- `apiFetch`: usa `credentials: 'include'` + sin localStorage
- `apiFetchForm`: usa `credentials: 'include'`
- Redirección 401 → `/login`

**`vite.config.ts`** (nuevo)
- Proxy Vite: `/api` → `http://localhost:8002` (mismo origen, cookies funcionan)

**`tsconfig.app.json`** (actualizado)
- Tests excluidos de compilación tsc

**Componentes adaptados**
- `Login.tsx`: `login()` sin argumento (token en cookie)
- `TickerModal.tsx`: `isAuthenticated` en vez de `token`
- `App.tsx`: loading state en ProtectedRoute
- `PaperTrading.tsx`: sin `token` de useAuth

### Tests — Actualizados

**`tests/conftest.py`**
- Fixture `disable_rate_limiting` (autouse) — evita que el rate limit interfiera entre suites
- `get_auth_headers` sigue usando Bearer (tests no tocan cookies)

**`tests/test_api/test_paper_trading.py`**
- Tests de auth no autorizada usan `client.cookies.clear()` para simular sin sesión

**Frontend tests**
- `AuthContext.test.tsx`: adaptado a nueva API (sin token, con isLoading)
- `ProtectedRoute.test.tsx`: mock de fetch + waitFor para comportamiento asíncrono

## Verificación

- ✅ 52/52 tests backend
- ✅ 4/4 tests frontend
- ✅ 3 errores TS preexistentes (sin nuevos)
- ✅ Cookies HttpOnly via `Set-Cookie` en login
- ✅ Bearer auth sigue funcionando (backward compat)
- ✅ Rate limiting funcional (10 req/60s)

## Archivos Modificados

| Archivo | Cambio |
|---|---|
| `backend/app/config.py` | TTL, cookie config, rate limit config |
| `backend/app/api/auth.py` | Cookies + rate limit + me/status/logout |
| `backend/app/core/deps.py` | Sub-dependencia cookie+Bearer + blacklist |
| `backend/tests/conftest.py` | Auto-disable rate limiting |
| `frontend-v2/src/context/AuthContext.tsx` | Sin localStorage, cookie-based |
| `frontend-v2/src/lib/api.ts` | credentials:'include' |
| `frontend-v2/vite.config.ts` | Proxy /api → backend |
| `frontend-v2/tsconfig.app.json` | Excluir tests |
| `frontend-v2/src/pages/Login.tsx` | login() sin argumento |
| `frontend-v2/src/components/TickerModal.tsx` | isAuthenticated |
| `frontend-v2/src/App.tsx` | Loading state |
| `frontend-v2/src/tabs/PaperTrading.tsx` | Sin token |

## Problemas Encontrados

1. **Rate limiting entre suites de test** — Auth tests agotaban el límite, paper trading tests fallaban. Resuelto con fixture `disable_rate_limiting` en conftest.
2. **Cookie persiste en TestClient** — Tests de no autorizado heredaban cookie del fixture `setup_account`. Corregido con `client.cookies.clear()`.
3. **`vi` global en TS** — Excluidos tests de `tsconfig.app.json` (vitest maneja su propia compilación).

## Score

| Dimensión | Antes (post-Ola 4) | Después |
|---|---|---|
| Auth/Seguridad | 6/10 | 8/10 |
| Frontend | 7/10 | 7.5/10 |
| **Global** | **8.5/10** | **9/10** |

---

*Ola 5 completada exitosamente.*
