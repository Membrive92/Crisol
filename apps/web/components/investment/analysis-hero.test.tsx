import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { AnalysisRun, Security } from '@crisol/types';

import { AnalysisHero } from './analysis-hero';

/**
 * El hero del informe (PHASE-44.24).
 *
 * Lo que se ata aquí es lo que un gate de TEXTO no puede: que el error de un
 * re-análisis se PINTE. La primera versión sólo comprobaba que la cadena
 * `rerunError` apareciera en el fichero — y aparece en la declaración de la
 * prop y en su JSDoc, así que vaciar el render la dejaba pasar.
 */

function run(partial: Partial<AnalysisRun> = {}): AnalysisRun {
  return {
    id: 'r1',
    security_id: 's1',
    run_date: '2026-06-01T00:00:00Z',
    engine_version: '1.7.0',
    thresholds_version: 'abc',
    years_covered: [2022, 2023, 2024],
    data_completeness: { value: '0.9' },
    verdict: {
      safety_profile: { label: 'watch', blocking_reasons: [] },
      dividend_verdict: 'healthy',
      questions: [],
    },
    flags: [],
    ...partial,
  } as unknown as AnalysisRun;
}

const security = {
  ticker: 'MCD',
  name: "McDonald's",
  sector: 'consumer_discretionary',
} as Security;

/** El hero exige un handler; estos tests no pulsan el botón. */
function noop(): void {
  return;
}

describe('AnalysisHero', () => {
  it('pinta el motivo por el que falló el re-análisis', () => {
    // El defecto: vivía sólo en la tarjeta de «aún no se ha analizado», que por
    // definición no está en pantalla cuando ya hay informe — que es justo
    // cuando se pulsa «Volver a analizar».
    render(
      <AnalysisHero
        security={security}
        run={run()}
        onRerun={noop}
        rerunning={false}
        printHref="/x?print=1"
        guideHref="/investments/analysis/guide"
        rerunError="No se pudo ejecutar el análisis."
      />,
    );
    expect(screen.getByText('No se pudo ejecutar el análisis.')).toBeTruthy();
  });

  it('sin error no pinta nada en su sitio', () => {
    render(
      <AnalysisHero
        security={security}
        run={run()}
        onRerun={noop}
        rerunning={false}
        printHref="/x?print=1"
        guideHref="/investments/analysis/guide"
      />,
    );
    expect(screen.queryByText(/No se pudo ejecutar/)).toBeNull();
  });

  it('el enlace a la guía es EXACTAMENTE el que le pasan (lleva la vuelta)', () => {
    // Un literal `/investments/analysis/guide` aquí perdería de dónde se
    // viene, y la guía volvería a ser un callejón sin salida.
    render(
      <AnalysisHero
        security={security}
        run={run()}
        onRerun={noop}
        rerunning={false}
        printHref="/x?print=1"
        guideHref="/investments/analysis/guide?back=%2Finvestments%2Fanalysis%2Fs1%3Ftab%3Dratios"
      />,
    );
    const enlace = screen.getByRole('link', { name: /Cómo leer este informe/ });
    expect(enlace.getAttribute('href')).toBe(
      '/investments/analysis/guide?back=%2Finvestments%2Fanalysis%2Fs1%3Ftab%3Dratios',
    );
  });

  it('el enlace del dictamen es EXACTAMENTE el que le pasan', () => {
    render(
      <AnalysisHero
        security={security}
        run={run()}
        onRerun={noop}
        rerunning={false}
        printHref="/investments/analysis/s1?run=r7&print=1"
        guideHref="/investments/analysis/guide?back=x"
      />,
    );
    const enlace = screen.getByRole('link', { name: /Dictamen imprimible/ });
    expect(enlace.getAttribute('href')).toBe('/investments/analysis/s1?run=r7&print=1');
  });
});
