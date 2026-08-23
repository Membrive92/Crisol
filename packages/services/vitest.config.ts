import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts'],
    // C0 (ciclo definido por el usuario) — El huso se FIJA, y no a UTC.
    //
    // La aritmética de períodos (`period/`) construye todos sus bordes con
    // `Date.UTC`, y hay tests que dicen protegerlo. Pero CI corre en
    // `ubuntu-latest`, o sea en UTC, y ahí `Date.UTC(y,m,d)` y
    // `new Date(y,m,d)` dan lo MISMO: cambiar una por otra pasaba los tests
    // en verde y desplazaba el corte del ciclo un día entero en el navegador
    // de cualquier usuario europeo (todas las transacciones del día 13
    // desaparecían del ciclo, y del siguiente, en silencio).
    //
    // Verificado por mutación: con TZ=UTC la sustitución pasa 52/52; con este
    // huso, cae. Es el mecanismo de [PHASE-44.17] «un gate que nunca ha
    // fallado puede estar mirando a otro lado»: sin fijar el huso, el gate no
    // existía. Europe/Madrid a propósito — es el del usuario, y por tanto el
    // que produce los fallos reales; cualquier huso ≠ UTC serviría.
    env: { TZ: 'Europe/Madrid' },
  },
});
