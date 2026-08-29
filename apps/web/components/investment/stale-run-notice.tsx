'use client';

import { Button } from '@/components/ui/button';
import { isRunOutdated, spacing } from '@crisol/ui';

import { DegradedPanel } from './degraded-panel';

export interface StaleRunNoticeProps {
  /** Versión del motor que produjo el análisis guardado. */
  runVersion: string | undefined;
  /** Versión del motor que corre AHORA, según el catálogo de métricas. */
  engineVersion: string | undefined;
  onRerun: () => void;
  rerunning: boolean;
}

/**
 * Avisa de que el informe en pantalla lo calculó un motor anterior (PHASE-44.16).
 *
 * **Por qué hace falta un aviso global y no basta con tolerar los huecos.** El
 * arreglo defensivo evita el crash y evita las frases falsas, pero deja al
 * usuario delante de un informe con métricas ausentes, comprobaciones en blanco
 * y veredictos «no auditables» sin una causa común a la vista. Cada hueco
 * explica lo suyo; sólo esto explica que todos son el mismo hueco.
 *
 * No se pinta cuando el run es POSTERIOR al catálogo — eso no es un análisis
 * caducado sino un frontend servido de una caché vieja, y mandar a reejecutar
 * un análisis sano sería el consejo equivocado.
 */
export function StaleRunNotice({
  runVersion,
  engineVersion,
  onRerun,
  rerunning,
}: StaleRunNoticeProps) {
  if (!isRunOutdated(runVersion, engineVersion)) return null;

  return (
    <DegradedPanel
      title="Este análisis lo calculó una versión anterior del motor"
      reason={`Se guardó con el motor ${runVersion} y ahora corre el ${engineVersion}. Un análisis es una foto: se conserva tal y como se calculó, así que las métricas que el motor no emitía entonces aparecen vacías con su motivo.`}
      consequence="Los números que sí están son válidos — se calcularon con los datos de su día. Vuelve a ejecutarlo para obtener el informe completo con los cortes y el desglose de señales actuales."
    >
      <Button
        variant="secondary"
        onClick={onRerun}
        disabled={rerunning}
        data-print="hide"
        style={{ alignSelf: 'flex-start', marginTop: spacing.xs }}
      >
        {rerunning ? 'Reejecutando…' : 'Volver a ejecutar el análisis'}
      </Button>
    </DegradedPanel>
  );
}
