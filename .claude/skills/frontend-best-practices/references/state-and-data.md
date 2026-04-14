# Gestión de estado y data fetching

## Tabla de contenidos
1. [Regla de oro: qué tipo de estado usar](#regla-de-oro)
2. [Zustand — estado del cliente](#zustand)
3. [TanStack Query — estado del servidor](#tanstack-query)
4. [API client y servicios](#api-client)
5. [Patrones de data flow](#patrones-de-data-flow)
6. [Antipatrones](#antipatrones)

---

## Regla de oro

Antes de crear estado, identificar su naturaleza:

| Pregunta | Tipo | Herramienta |
|----------|------|-------------|
| ¿Viene de una API/servidor? | Estado servidor | TanStack Query |
| ¿Es UI local (modal abierto, tab activo)? | Estado local | `useState` / `useReducer` |
| ¿Necesita compartirse entre pantallas sin prop drilling? | Estado cliente global | Zustand |
| ¿Es un formulario? | Estado de formulario | React Hook Form (si hay complejidad) o `useState` |

**NUNCA** duplicar estado del servidor en Zustand. Si un dato viene de la API, 
TanStack Query es su fuente de verdad — no copiar a un store.

---

## Zustand

### Estructura de un store

```
packages/store/src/
├── auth-store.ts
├── ui-store.ts
├── preferences-store.ts
└── index.ts
```

### Patrón estándar

```typescript
// packages/store/src/auth-store.ts

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import AsyncStorage from '@react-native-async-storage/async-storage';
import type { AuthSession, User } from '@app/types';

interface AuthState {
  /** Sesión actual o null si no autenticado */
  session: AuthSession | null;
  /** Usuario actual */
  user: User | null;
  /** Indica si la hidratación inicial ha terminado */
  isHydrated: boolean;
}

interface AuthActions {
  /** Establece la sesión tras login exitoso */
  setSession: (session: AuthSession) => void;
  /** Establece datos del usuario */
  setUser: (user: User) => void;
  /** Limpia toda la sesión (logout) */
  clearSession: () => void;
  /** Marca la hidratación como completada */
  setHydrated: () => void;
}

const INITIAL_STATE: AuthState = {
  session: null,
  user: null,
  isHydrated: false,
};

export const useAuthStore = create<AuthState & AuthActions>()(
  persist(
    (set) => ({
      ...INITIAL_STATE,

      setSession: (session) => set({ session }),
      setUser: (user) => set({ user }),
      clearSession: () => set({ ...INITIAL_STATE, isHydrated: true }),
      setHydrated: () => set({ isHydrated: true }),
    }),
    {
      name: 'auth-storage',
      storage: createJSONStorage(() => AsyncStorage),
      partialize: (state) => ({
        session: state.session,
        user: state.user,
      }),
      onRehydrateStorage: () => (state) => {
        state?.setHydrated();
      },
    }
  )
);
```

### Reglas de Zustand

1. **Un store por dominio** — no un store gigante. `auth-store`, `ui-store`, `preferences-store`.
2. **Separar state de actions** en la interface para claridad.
3. **Selectores granulares** — NUNCA suscribirse al store entero.

```typescript
// ❌ MAL — Se re-renderiza con CUALQUIER cambio del store
const store = useAuthStore();

// ✅ BIEN — Solo se re-renderiza cuando user cambia
const user = useAuthStore((state) => state.user);
const isLoggedIn = useAuthStore((state) => state.session !== null);
```

4. **Derived state** con funciones, no con estado duplicado.

```typescript
// ❌ MAL — Estado derivado almacenado
interface State {
  items: Item[];
  totalPrice: number;  // ← Duplicado, se desincroniza
}

// ✅ BIEN — Calcular al consumir
const totalPrice = useCartStore((state) =>
  state.items.reduce((sum, item) => sum + item.price * item.quantity, 0)
);
```

5. **`persist` solo para datos que sobreviven al cierre** — sesión, preferencias, onboarding. 
   NUNCA persistir estado de UI.

---

## TanStack Query

### Estructura

```
packages/services/src/
├── queries/
│   ├── query-keys.ts            # Factory de keys centralizado
│   ├── useUserQuery.ts
│   ├── useProductsQuery.ts
│   ├── useAuthMutation.ts
│   └── index.ts
```

### Query Key Factory

Centralizar TODAS las query keys para evitar inconsistencias y facilitar invalidaciones:

```typescript
// packages/services/src/queries/query-keys.ts

export const queryKeys = {
  users: {
    all: ['users'] as const,
    lists: () => [...queryKeys.users.all, 'list'] as const,
    list: (filters: UserFilters) => [...queryKeys.users.lists(), filters] as const,
    details: () => [...queryKeys.users.all, 'detail'] as const,
    detail: (id: string) => [...queryKeys.users.details(), id] as const,
  },
  products: {
    all: ['products'] as const,
    lists: () => [...queryKeys.products.all, 'list'] as const,
    list: (filters: ProductFilters) => [...queryKeys.products.lists(), filters] as const,
    detail: (id: string) => [...queryKeys.products.all, 'detail', id] as const,
  },
} as const;
```

### Patrón de query hook

```typescript
// packages/services/src/queries/useUserQuery.ts

import { useQuery } from '@tanstack/react-query';
import { queryKeys } from './query-keys';
import { usersApi } from '../api/endpoints/users';
import { mapUserDtoToUser } from '../mappers/user-mapper';
import type { User } from '@app/types';

/**
 * Obtiene los datos de un usuario por ID.
 * 
 * @param userId - ID del usuario
 * @returns Query result con User mapeado del dominio
 * 
 * @example
 * ```tsx
 * const { data: user, isLoading } = useUserQuery('user-123');
 * ```
 */
export function useUserQuery(userId: string) {
  return useQuery({
    queryKey: queryKeys.users.detail(userId),
    queryFn: async (): Promise<User> => {
      const dto = await usersApi.getUser(userId);
      return mapUserDtoToUser(dto);
    },
    enabled: Boolean(userId),
    staleTime: 5 * 60 * 1000, // 5 minutos
  });
}
```

### Patrón de mutation hook

```typescript
// packages/services/src/queries/useAuthMutation.ts

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { authApi } from '../api/endpoints/auth';
import { useAuthStore } from '@app/store';
import { queryKeys } from './query-keys';
import type { LoginCredentials } from '@app/types';

export function useLoginMutation() {
  const queryClient = useQueryClient();
  const setSession = useAuthStore((state) => state.setSession);

  return useMutation({
    mutationFn: (credentials: LoginCredentials) => authApi.login(credentials),
    onSuccess: (data) => {
      setSession(data.session);
      // Invalidar queries que dependan de auth
      queryClient.invalidateQueries({ queryKey: queryKeys.users.all });
    },
  });
}
```

### Reglas de TanStack Query

1. **staleTime por defecto razonable** — configurar en el QueryClient, no en cada query.

```typescript
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60 * 1000,       // 1 minuto
      gcTime: 5 * 60 * 1000,      // 5 minutos
      retry: 2,
      refetchOnWindowFocus: false, // Evitar refetch agresivo en móvil
    },
  },
});
```

2. **`enabled` para queries condicionales** — nunca hacer fetch si no hay datos necesarios.
3. **Invalidar, no setear** — tras una mutation, invalidar la query para que refetche.
4. **Optimistic updates** solo cuando la UX lo justifique (likes, toggles).

---

## API client

### Cliente base

```typescript
// packages/services/src/api/client.ts

import { useAuthStore } from '@app/store';
import type { ApiResponse, ApiError } from '@app/types';

const API_BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? process.env.NEXT_PUBLIC_API_URL;

interface RequestConfig extends Omit<RequestInit, 'body'> {
  body?: unknown;
  params?: Record<string, string>;
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  private getHeaders(): HeadersInit {
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    };

    const session = useAuthStore.getState().session;
    if (session?.accessToken) {
      headers['Authorization'] = `Bearer ${session.accessToken}`;
    }

    return headers;
  }

  private buildUrl(path: string, params?: Record<string, string>): string {
    const url = new URL(path, this.baseUrl);
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        url.searchParams.set(key, value);
      });
    }
    return url.toString();
  }

  async request<T>(path: string, config: RequestConfig = {}): Promise<T> {
    const { body, params, ...init } = config;

    const response = await fetch(this.buildUrl(path, params), {
      ...init,
      headers: { ...this.getHeaders(), ...init.headers },
      body: body ? JSON.stringify(body) : undefined,
    });

    if (!response.ok) {
      const error: ApiError = await response.json().catch(() => ({
        message: 'Error de red',
        statusCode: response.status,
      }));
      throw error;
    }

    return response.json() as Promise<T>;
  }

  get<T>(path: string, params?: Record<string, string>) {
    return this.request<T>(path, { method: 'GET', params });
  }

  post<T>(path: string, body?: unknown) {
    return this.request<T>(path, { method: 'POST', body });
  }

  put<T>(path: string, body?: unknown) {
    return this.request<T>(path, { method: 'PUT', body });
  }

  patch<T>(path: string, body?: unknown) {
    return this.request<T>(path, { method: 'PATCH', body });
  }

  delete<T>(path: string) {
    return this.request<T>(path, { method: 'DELETE' });
  }
}

export const apiClient = new ApiClient(API_BASE_URL ?? '');
```

### Endpoints

```typescript
// packages/services/src/api/endpoints/users.ts

import { apiClient } from '../client';
import type { UserDto, UpdateUserDto } from '@app/types';

export const usersApi = {
  getUser: (id: string) =>
    apiClient.get<UserDto>(`/users/${id}`),

  updateUser: (id: string, data: UpdateUserDto) =>
    apiClient.patch<UserDto>(`/users/${id}`, data),

  listUsers: (params?: { page?: string; limit?: string }) =>
    apiClient.get<{ data: UserDto[]; total: number }>('/users', params),
};
```

### Mappers (DTO → Domain Model)

```typescript
// packages/services/src/mappers/user-mapper.ts

import type { UserDto } from '@app/types';
import type { User } from '@app/types';

/**
 * Transforma el DTO de la API al modelo de dominio del frontend.
 * Esto desacopla el frontend de la estructura exacta de la API.
 */
export function mapUserDtoToUser(dto: UserDto): User {
  return {
    id: dto.id,
    fullName: `${dto.first_name} ${dto.last_name}`,
    email: dto.email,
    avatarUrl: dto.avatar_url ?? null,
    role: dto.role,
    createdAt: new Date(dto.created_at),
  };
}
```

---

## Patrones de data flow

### Flujo completo: pantalla → query → API → componente

```
┌─────────────────────────────────────────────┐
│  apps/web/  o  apps/mobile/                 │
│                                             │
│  ProfileScreen                              │
│  ├── useUserQuery(userId)  ← TanStack Query │
│  ├── useAuthStore()        ← Zustand        │
│  └── <ProfileCard user={data} />  ← UI pura │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│  packages/services/                          │
│  useUserQuery → usersApi.getUser → apiClient │
│               → mapUserDtoToUser             │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│  packages/ui/                                │
│  <ProfileCard user={User} />  ← Solo props  │
│  Sin fetch, sin store, sin side effects      │
└─────────────────────────────────────────────┘
```

---

## Antipatrones

```typescript
// ❌ 1. Duplicar estado del servidor en Zustand
const useProductStore = create((set) => ({
  products: [],
  fetchProducts: async () => {
    const data = await api.getProducts(); // ← Esto es TanStack Query
    set({ products: data });
  },
}));

// ❌ 2. useEffect + useState para fetching
const [data, setData] = useState(null);
const [loading, setLoading] = useState(true);
useEffect(() => {
  api.getUser(id).then(setData).finally(() => setLoading(false));
}, [id]);
// ← Usar useUserQuery(id) en su lugar

// ❌ 3. Query keys hardcodeadas
useQuery({ queryKey: ['users', id] }); // ← Usar queryKeys.users.detail(id)

// ❌ 4. Fetch dentro de componentes UI (packages/ui/)
// Los componentes compartidos NUNCA hacen fetch

// ❌ 5. Store sin selectores
const { user, session, theme, notifications } = useAuthStore();
// ← Suscripción al store entero, re-render en cualquier cambio
```
