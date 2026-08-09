/**
 * Escala divergente para el heatmap de variaciones (PHASE-44.22).
 *
 * Capa PURA (ADR-0001: `packages/ui` son tokens y funciones, no componentes), y
 * compartida a propósito: el día que móvil pinte el heatmap, el corte de las
 * bandas y el color de cada una ya están decididos aquí. Dos implementaciones
 * del mismo semáforo acabarían discrepando sobre la misma empresa.
 *
 * ## Por qué el número va SIEMPRE impreso en la celda
 *
 * No es una preferencia. Los dos polos de esta escala son el verde y el rojo de
 * la casa, que es lo que el resto de la aplicación usa para bueno/malo — y
 * medido con el simulador de Machado-Oliveira-Fernandes, un protanope ve el
 * extremo de caída y el de crecimiento a **ΔE 2,6** (OKLab ×100). Es decir: no
 * los distingue. Con el valor y su signo escritos dentro, el color refuerza una
 * lectura que ya está completa sin él; sin el valor, la celda mentiría a una de
 * cada doce personas.
 *
 * Los pasos de cada lado sí pasan las comprobaciones de rampa ordinal
 * (monotonía de luminosidad, salto mínimo entre pasos y extremo claro
 * despegado del fondo blanco), verificadas con el validador, no a ojo.
 */

/** Un paso de la escala: fondo de la celda y tinta que se lee encima. */
export interface DivergingStep {
  background: string;
  foreground: string;
}

/**
 * Cortes en tanto por uno sobre la variación interanual.
 *
 * Tres bandas por lado, y por tanto TRES cortes: con dos, el paso más claro de
 * cada rampa no se alcanzaba nunca — un color declarado y muerto, que es la
 * misma familia que una exención razonada que no se ejecuta.
 *
 * ±2% es ruido contable en cualquier magnitud; a partir del 10% hay un
 * movimiento que mirar; por encima del 25%, uno que explicar. Los cortes son
 * simétricos a propósito: una escala divergente con los lados desiguales
 * convierte una asimetría de diseño en una conclusión sobre la empresa.
 */
export const DELTA_BREAKS = { noise: 0.02, moderate: 0.1, strong: 0.25 } as const;

const NEUTRAL: DivergingStep = { background: '#f5f5f5', foreground: '#1f1f1f' };

/** Crecimiento: claro → oscuro. Validado como rampa ordinal. */
const GROWTH: DivergingStep[] = [
  { background: '#7cc47f', foreground: '#1f1f1f' },
  { background: '#35933a', foreground: '#ffffff' },
  { background: '#14481a', foreground: '#ffffff' },
];

/** Caída: claro → oscuro. Validado como rampa ordinal. */
const DECLINE: DivergingStep[] = [
  { background: '#ef9a9a', foreground: '#1f1f1f' },
  { background: '#e05252', foreground: '#ffffff' },
  { background: '#b71c1c', foreground: '#ffffff' },
];

/** Celda sin dato: ni verde ni roja. Un hueco no es un cero. */
export const NO_DATA_STEP: DivergingStep = { background: 'transparent', foreground: '#767676' };

/**
 * El paso que le toca a una variación interanual.
 *
 * `null` (no hay dato) NO cae al neutro: el neutro significa «se midió y no se
 * movió», y confundirlo con «no se pudo medir» es la convención hueco ≠ 0 que
 * el motor aplica desde PHASE-44.2 §4.5, rota en la última milla.
 */
export function deltaStep(yoy: number | null): DivergingStep {
  if (yoy === null || !Number.isFinite(yoy)) return NO_DATA_STEP;
  const magnitude = Math.abs(yoy);
  if (magnitude < DELTA_BREAKS.noise) return NEUTRAL;
  const ramp = yoy > 0 ? GROWTH : DECLINE;
  const index =
    magnitude >= DELTA_BREAKS.strong ? 2 : magnitude >= DELTA_BREAKS.moderate ? 1 : 0;
  return ramp[index] as DivergingStep;
}

/**
 * Las cinco entradas de la leyenda, en el orden en que se leen (de caída fuerte
 * a crecimiento fuerte). Se derivan de los mismos cortes que pintan las celdas:
 * una leyenda escrita a mano es la premisa que caduca en silencio de PHASE-43.
 */
export function deltaLegend(): { label: string; step: DivergingStep }[] {
  const strong = Math.round(DELTA_BREAKS.strong * 100);
  const moderate = Math.round(DELTA_BREAKS.moderate * 100);
  const noise = Math.round(DELTA_BREAKS.noise * 100);
  const mid = (DELTA_BREAKS.moderate + DELTA_BREAKS.strong) / 2;
  const low = (DELTA_BREAKS.noise + DELTA_BREAKS.moderate) / 2;
  return [
    { label: `≤ −${strong}%`, step: deltaStep(-DELTA_BREAKS.strong) },
    { label: `−${strong}% a −${moderate}%`, step: deltaStep(-mid) },
    { label: `−${moderate}% a −${noise}%`, step: deltaStep(-low) },
    { label: `±${noise}%`, step: deltaStep(0) },
    { label: `+${noise}% a +${moderate}%`, step: deltaStep(low) },
    { label: `+${moderate}% a +${strong}%`, step: deltaStep(mid) },
    { label: `≥ +${strong}%`, step: deltaStep(DELTA_BREAKS.strong) },
  ];
}
