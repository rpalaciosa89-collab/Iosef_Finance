# Ola 5 — Backup del estado post-Ola-4

**Fecha:** 2026-06-10

## Estado actual de Auth

### Backend: app/core/security.py
- JWT generado con `python-jose`, algoritmo HS256
- TTL: 7 días (ACCESS_TOKEN_EXPIRE_MINUTES)
- Token devuelto como JSON en body (`{"access_token": "..."}`)
- Login vía OAuth2PasswordRequestForm en `/api/auth/token`

### Backend: app/core/deps.py
- `get_current_user` extrae token del header Authorization Bearer
- No existe logout (sin blacklist)

### Frontend: context/AuthContext.tsx
- Token guardado en localStorage (`iosef_auth_token`)
- Vulnerable a XSS (cualquier script puede leerlo)

### Frontend: lib/api.ts
- `apiFetch` lee token de localStorage, lo pone en header
- `apiFetchForm` para login (form-urlencoded)
- En 401 → redirect a /login

### Sin rate limiting, sin logout, sin cookies HttpOnly

## Hallazgos a resolver:
- H-003 (Alta): Token JWT en localStorage (XSS vulnerable)
- H-015 (Alta): Sin rate limiting en auth
- H-018 (Media): Sin endpoint de logout
- H-021 (Baja): TTL de 7 días demasiado largo
