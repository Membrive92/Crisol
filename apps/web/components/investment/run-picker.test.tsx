import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import type { AnalysisRunSummary } from '@crisol/types';

import { RunPicker } from './run-picker';

/**
 * El histórico de análisis (PHASE-44.24.F).
 *
 * Lo que se ata aquí es la SALIDA: la comparación se entraba pulsando
 * «comparar» y no había ningún gesto para deshacerla, así que el estado se
 * quedaba pegado hasta editar la URL a mano.
 */

function run(id: string, partial: Partial<AnalysisRunSummary> = {}): AnalysisRunSummary {
  return {
    id,
    run_date: '2026-08-28T00:00:00Z',
    engine_version: '1.7.0',
    thresholds_version: 'abc',
    years_covered: [2024, 2025],
    m_score: null,
    z_score: null,
    f_score: null,
    dividend_verdict: null,
    confidence: '1.0',
    ...partial,
  };
}

describe('RunPicker', () => {
  it('elegir una base la comunica con su id', () => {
    const onCompare = vi.fn();
    render(
      <RunPicker
        runs={[run('a'), run('b')]}
        selectedId="a"
        compareId={null}
        onSelect={vi.fn()}
        onCompare={onCompare}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /comparar/i }));

    expect(onCompare).toHaveBeenCalledWith('b');
  });

  it('la base pulsada otra vez SALE de la comparación', () => {
    // Sin esto la comparación es de un solo sentido: se entra y no se puede
    // volver. El botón tiene que decir la acción, no el estado — «comparando»
    // se lee como un progreso en curso.
    const onCompare = vi.fn();
    render(
      <RunPicker
        runs={[run('a'), run('b')]}
        selectedId="a"
        compareId="b"
        onSelect={vi.fn()}
        onCompare={onCompare}
      />,
    );

    const salir = screen.getByRole('button', { name: /dejar de comparar/i });
    expect(salir.getAttribute('aria-pressed')).toBe('true');

    fireEvent.click(salir);

    expect(onCompare).toHaveBeenCalledWith(null);
  });

  it('la fila actual ofrece la salida cuando ADEMÁS es la base', () => {
    // Con `run` y `compare` iguales (una URL pegada) el servidor responde «no
    // se puede comparar un análisis consigo mismo». Sin este botón el usuario
    // se queda con el error y sin ningún gesto para quitarlo.
    const onCompare = vi.fn();
    render(
      <RunPicker
        runs={[run('a'), run('b')]}
        selectedId="a"
        compareId="a"
        onSelect={vi.fn()}
        onCompare={onCompare}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /dejar de comparar/i }));

    expect(onCompare).toHaveBeenCalledWith(null);
  });

  it('el ⚠ se explica SÓLO cuando alguna fila lo lleva', () => {
    // El aviso se deriva de lo que se pinta: explicar un símbolo que no está
    // en pantalla es ruido, y dejarlo sin explicar lo vuelve mudo. La segunda
    // fila lleva otro motor, así que aquí SÍ toca.
    const { rerender } = render(
      <RunPicker
        runs={[run('a'), run('b', { engine_version: '1.6.0' })]}
        selectedId="a"
        compareId={null}
        onSelect={vi.fn()}
        onCompare={vi.fn()}
      />,
    );
    expect(screen.getByText(/sólo se dirá qué cambió del MÉTODO/i)).toBeDefined();

    // Con todas del mismo motor no hay ningún ⚠ que explicar.
    rerender(
      <RunPicker
        runs={[run('a'), run('b')]}
        selectedId="a"
        compareId={null}
        onSelect={vi.fn()}
        onCompare={vi.fn()}
      />,
    );
    expect(screen.queryByText(/sólo se dirá qué cambió del MÉTODO/i)).toBeNull();
  });

  it('dice qué produce cada gesto, no sólo cómo se llaman', () => {
    // «Elige cuál miras y contra cuál lo comparas» nombraba los dos gestos sin
    // decir qué hacía ninguno: «comparar» sólo se entendía pulsándolo.
    render(
      <RunPicker
        runs={[run('a'), run('b')]}
        selectedId="a"
        compareId={null}
        onSelect={vi.fn()}
        onCompare={vi.fn()}
      />,
    );
    expect(screen.getByText(/ABRIR ese análisis/i)).toBeDefined();
    expect(screen.getByText(/qué se ha movido entre los dos/i)).toBeDefined();
    expect(screen.getByText(/scores forenses/i)).toBeDefined();
  });

  it('la fila actual NO ofrece comparar contra sí misma', () => {
    render(
      <RunPicker
        runs={[run('a'), run('b')]}
        selectedId="a"
        compareId={null}
        onSelect={vi.fn()}
        onCompare={vi.fn()}
      />,
    );

    // Sólo la otra fila: comparar el actual contra el actual es el 404 del
    // servidor.
    expect(screen.getAllByRole('button', { name: /^comparar$/i })).toHaveLength(1);
  });
});
