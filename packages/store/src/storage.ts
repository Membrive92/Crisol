import { createJSONStorage, type PersistStorage } from 'zustand/middleware';

/**
 * Adapter de persistencia para Zustand — versión **web** (default).
 *
 * Metro escoge automáticamente `./storage.native.ts` en mobile; cualquier
 * otro bundler (Next.js / Vite / Webpack) ve este archivo. Mantenemos
 * el `localStorage` directo (mismo comportamiento que pre-PHASE-11.2).
 *
 * Devuelve `undefined` durante SSR (Node, donde `localStorage` no existe).
 * `createJSONStorage` ya tolera ese caso: con storage `undefined` no
 * persiste y los componentes leen el initial state hasta hidratar
 * cliente.
 */
export const storage = createJSONStorage(() => {
  if (typeof window === 'undefined') {
    return undefined as unknown as Storage;
  }
  return localStorage;
}) as PersistStorage<unknown>;
