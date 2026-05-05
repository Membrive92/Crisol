import AsyncStorage from '@react-native-async-storage/async-storage';
import { createJSONStorage, type PersistStorage } from 'zustand/middleware';

/**
 * Adapter de persistencia para Zustand — versión **React Native**.
 *
 * Metro escoge este archivo automáticamente vía la extensión `.native.ts`
 * cuando el bundle es para iOS/Android. Web/SSR ven `./storage.ts`
 * (sin `.native`), que usa `localStorage`.
 *
 * `AsyncStorage` es asíncrono — Zustand persist espera la lectura
 * inicial antes de marcar el store como hidratado, idéntico patrón
 * que `localStorage`.
 */
export const storage = createJSONStorage(() => AsyncStorage) as PersistStorage<unknown>;
