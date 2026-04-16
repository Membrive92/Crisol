# PHASE-1.2 — Auth frontend

**Estado**: ✅ completada
**Rama**: `feat/phase-1.2-auth-frontend`
**PR**: —
**Fecha de merge**: 2026-04-14

> Documento redactado retroactivamente en PHASE-2.2.

## Objetivo

Consumir el backend de autenticación (PHASE-1.1) desde las dos aplicaciones
del monorepo: pantallas de login/registro en web (Next.js) y móvil (Expo),
con sesión persistente y refresh automático de tokens.

## Qué se implementó

- Cliente HTTP compartido en `packages/services`:
  - `apiClient` (axios) con `configureApi({ baseURL })`.
  - Interceptor request: adjunta `Authorization: Bearer <accessToken>`.
  - Interceptor response 401: cola de reintentos, llamada a
    `POST /auth/refresh`, rotación de tokens y reintento transparente.
  - Callback `setOnAuthFailure` para que cada app decida cómo limpiar sesión.
- `authApi` con: `register`, `login`, `refresh`, `logout`, `getMe`.
- Store Zustand en `packages/store` (`useAuthStore`) con:
  - `user`, `accessToken`, `refreshToken`, `isAuthenticated`, `isHydrated`.
  - Acciones `setTokens`, `setUser`, `hydrate`, `logout`.
- Tipos compartidos en `packages/types`: `User`, `LoginRequest`,
  `RegisterRequest`, `RefreshRequest`, `TokenResponse`.
- Web (`apps/web`):
  - `AuthProvider` que configura la API, hidrata desde `localStorage`
    (refresh token) y suscribe al store para mantener el token vivo.
  - Rutas `(auth)/login`, `(auth)/register` y layout centrado.
  - Rutas `(dashboard)/home` con guard que redirige a `/login` si no hay
    sesión y refresca tokens al montar.
- Mobile (`apps/mobile`):
  - Hook `useAuthInit` con la misma lógica que el AuthProvider pero usando
    `expo-secure-store` en lugar de `localStorage`.
  - Rutas `(auth)/login`, `(auth)/register` y `(tabs)/home`.
  - `RootLayout` redirige entre `(auth)` y `(tabs)` según estado.

## Flujo técnico

```
Login (web/mobile)
  │
  ├─ POST /auth/login → TokenResponse
  │      └─ setTokens + getMe → setUser
  │
  ├─ Refresh (al volver a la app)
  │   refreshToken en storage → POST /auth/refresh → nuevos tokens
  │
  ├─ Interceptor 401
  │   request falla 401 → attemptRefresh() → retry original request
  │      (si refresh falla → onAuthFailure → logout)
  │
  └─ Logout
      POST /auth/logout(refreshToken) + clearAuth + borrar storage
```

## Archivos clave

- `packages/services/src/api/client.ts` — axios + interceptores.
- `packages/services/src/api/endpoints/auth.ts` — llamadas al backend.
- `packages/store/src/auth.ts` — store Zustand de sesión.
- `packages/types/src/dto/auth.dto.ts` — DTOs.
- `apps/web/lib/auth-provider.tsx` — bootstrap web.
- `apps/web/app/(auth)/login/page.tsx` — login web.
- `apps/web/app/(auth)/register/page.tsx` — registro web.
- `apps/web/app/(dashboard)/layout.tsx` — guard autenticación.
- `apps/mobile/lib/auth-provider.tsx` — bootstrap mobile.
- `apps/mobile/app/(auth)/login.tsx` — login mobile.
- `apps/mobile/app/(auth)/register.tsx` — registro mobile.

## Decisiones tomadas

- **Refresh token en `localStorage` (web)**: para el MVP local basta. En
  despliegue futuro se pasará a cookie `httpOnly` vía backend. Documentado en
  `internal_docs/architecture.md` §7.
- **Sin TanStack Query aún**: la auth es puntual y no se beneficia de cache.
  Se introducirá en PHASE-2.2 para transacciones.

## Limitaciones conocidas

- No hay persistencia del perfil (`user`) en storage — se recupera con `getMe`
  en cada recarga. Intencional.
- Sin estilos compartidos entre web y mobile — cada app usa su patrón propio
  (inline en web, `StyleSheet` en mobile). Se revisará si se introduce
  NativeWind.

## Verificación

- [x] Login y registro funcionan contra backend local.
- [x] Refresh automático verificado con access token caducado.
- [x] Logout limpia tokens en cliente y storage.
- [x] `pnpm lint && pnpm typecheck` verde.

## Próxima fase

PHASE-2.1 — Transactions backend.
