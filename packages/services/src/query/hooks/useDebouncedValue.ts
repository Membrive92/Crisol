import { useEffect, useState } from 'react';

/**
 * Devuelve `value` retrasado `delayMs` desde el último cambio.
 *
 * Pensado para lo que se teclea: mientras el usuario escribe, el valor devuelto
 * se queda quieto, así que la query que lo consume no se relanza en cada
 * pulsación. Introducido en PHASE-44.8 E1, donde el buscador de valores emitía
 * una petición por tecla.
 *
 * El timeout se cancela en la limpieza del efecto, así que sólo sobrevive el
 * último cambio; y el primer render devuelve ya el valor inicial, para que un
 * campo precargado (por ejemplo desde la URL) no tarde en resolverse. Cuando el
 * valor no ha cambiado, el `setState` recibe el mismo valor y React descarta el
 * re-render — por eso no hace falta cortocircuitar a mano.
 *
 * Cross-platform: sólo usa `setTimeout`, disponible igual en web y en React
 * Native.
 *
 * @param value - Valor que cambia con frecuencia.
 * @param delayMs - Milisegundos de calma exigidos antes de propagarlo.
 * @returns El último valor que se mantuvo estable `delayMs`.
 */
export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);

  return debounced;
}
