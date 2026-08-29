import type {
  FlagHelp,
  HelpCatalogResponse,
  ScoreComponentHelp,
  ScoreHelp,
} from '@crisol/types';

/**
 * Índice de las fichas de score del engine (PHASE-44.24.A).
 *
 * Capa PURA (ADR-0001): sólo indexa lo que el servidor manda, no hace fetching
 * ni escribe un solo texto. Vive aquí y no en `apps/web` porque la tarjeta de
 * desglose la van a pintar las dos apps, y una copia del índice en cada una es
 * cómo se llega a que una pantalla enseñe la etiqueta y la otra la clave cruda
 * — que es literalmente el defecto que esta entrega viene a cerrar.
 */

export interface ScoreHelpIndex {
  /** La ficha de un score, o `undefined` si el catálogo no ha cargado. */
  score(scoreKey: string): ScoreHelp | undefined;
  /**
   * Nombre legible de una variable de un score.
   *
   * Cae a la CLAVE CRUDA cuando no hay catálogo. Es feo a propósito: antes que
   * inventar un nombre o dejar el hueco en blanco, se enseña lo que el motor
   * usa. Un gate del backend garantiza que ese camino no ocurra con una
   * variable real y el catálogo cargado.
   */
  componentLabel(scoreKey: string, componentKey: string): string;
  /** Qué es esa variable, para el `title`. `undefined` si no hay catálogo. */
  componentHelp(scoreKey: string, componentKey: string): ScoreComponentHelp | undefined;
  /** La ficha de una bandera, o `undefined` si el catálogo no ha cargado. */
  flag(flagKey: string): FlagHelp | undefined;
  /** `true` si el catálogo se ha podido cargar. */
  ready: boolean;
  /**
   * La versión del motor que sirve el catálogo, para comparar con la del run.
   *
   * `undefined` mientras no ha cargado: sin ella no se puede saber si un run
   * está caducado, y declararlo caducado sería inventárselo (PHASE-44.16).
   */
  engineVersion: string | undefined;
}

export function buildScoreHelpIndex(catalog: HelpCatalogResponse | undefined): ScoreHelpIndex {
  const scores = catalog?.scores ?? [];
  const byFlag = new Map<string, FlagHelp>((catalog?.flags ?? []).map((f) => [f.key, f]));
  const byScore = new Map<string, ScoreHelp>(scores.map((entry) => [entry.key, entry]));
  const byComponent = new Map<string, ScoreComponentHelp>();
  for (const entry of scores) {
    for (const component of entry.components) {
      byComponent.set(`${entry.key}|${component.key}`, component);
    }
  }
  return {
    score: (scoreKey) => byScore.get(scoreKey),
    componentHelp: (scoreKey, componentKey) => byComponent.get(`${scoreKey}|${componentKey}`),
    componentLabel: (scoreKey, componentKey) =>
      byComponent.get(`${scoreKey}|${componentKey}`)?.label ?? componentKey,
    flag: (flagKey) => byFlag.get(flagKey),
    ready: scores.length > 0,
    engineVersion: catalog?.engine_version,
  };
}
