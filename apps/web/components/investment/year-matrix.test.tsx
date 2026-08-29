import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { MatrixRow } from '@crisol/ui';

import { YearMatrix } from './year-matrix';

/*
 * PHASE-44.23 — la «i» que dice qué es cada fila.
 *
 * El informe pinta 64 métricas y 49 partidas con su valor, su unidad y su
 * banda, y la única pista de qué eran era la etiqueta. «Prueba ácida» y «Ratio
 * de caja» son cosas distintas y quien no las conozca no puede saber cuál está
 * leyendo.
 *
 * Lo que se comprueba aquí es el AFORDANCE, no el texto: el texto lo garantiza
 * el gate del backend (`test_investment_engine_contract.py`), que exige una
 * definición por métrica y por partida. Aquí, que la fila la ofrezca cuando
 * existe y NO la ofrezca cuando no — un ⓘ que abre un panel vacío es peor que
 * no tener ⓘ.
 */

function fila(key: string, label: string, help?: string): MatrixRow {
  return {
    key,
    label,
    // El caso «backend anterior al glosario» se escribe OMITIENDO la clave, no
    // poniéndola a cadena vacía: con '' el test pasaría por otra razón.
    ...(help === undefined ? {} : { help }),
    cells: [{ text: '1,42' }],
  };
}

const DEF = 'Activo corriente entre pasivo corriente: cuántas veces cubre lo que debe a un año.';

describe('YearMatrix · la ⓘ de cada fila', () => {
  it('ofrece la definición cuando la fila la trae', () => {
    render(<YearMatrix years={[2026]} rows={[fila('L1', 'Ratio corriente', DEF)]} />);
    expect(screen.getByRole('button', { name: 'Qué es «Ratio corriente»' })).toBeTruthy();
  });

  it('no la ofrece cuando la fila no la trae', () => {
    render(<YearMatrix years={[2026]} rows={[fila('L1', 'Ratio corriente')]} />);
    expect(screen.queryByRole('button', { name: /Qué es/ })).toBeNull();
  });

  it('al pulsarla despliega el texto, y al volver a pulsar lo cierra', () => {
    render(<YearMatrix years={[2026]} rows={[fila('L1', 'Ratio corriente', DEF)]} />);
    const boton = screen.getByRole('button', { name: 'Qué es «Ratio corriente»' });

    expect(screen.queryByText(DEF)).toBeNull();
    expect(boton.getAttribute('aria-expanded')).toBe('false');

    fireEvent.click(boton);
    expect(screen.getByText(DEF)).toBeTruthy();
    expect(boton.getAttribute('aria-expanded')).toBe('true');

    fireEvent.click(boton);
    expect(screen.queryByText(DEF)).toBeNull();
  });

  it('sólo hay una definición abierta a la vez', () => {
    // Con 49 partidas en la pantalla de Estados, varias abiertas convierten la
    // tabla en un muro de texto y tapan justo lo que se venía a comparar.
    const otra = 'Efectivo y depósitos disponibles de inmediato.';
    render(
      <YearMatrix
        years={[2026]}
        rows={[fila('L1', 'Ratio corriente', DEF), fila('cash', 'Efectivo', otra)]}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Qué es «Ratio corriente»' }));
    expect(screen.getByText(DEF)).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: 'Qué es «Efectivo»' }));
    expect(screen.getByText(otra)).toBeTruthy();
    expect(screen.queryByText(DEF)).toBeNull();
  });

  it('una cabecera de bloque no ofrece definición', () => {
    // No es un concepto: es un separador («Activo corriente»).
    render(
      <YearMatrix
        years={[2026]}
        rows={[{ key: 'g', label: 'Activo corriente', isGroup: true, help: DEF, cells: [] }]}
      />,
    );
    expect(screen.queryByRole('button', { name: /Qué es/ })).toBeNull();
  });
});

/**
 * El destino del enlace (PHASE-44.24.C.4): la fila se marca y se busca sola.
 *
 * El efecto vive en la fila y no en el origen porque `TabPanel` desmonta las
 * pestañas inactivas: cuando se pulsa el enlace, esta tabla todavía no existe.
 */
describe('YearMatrix: la fila a la que se ha llegado', () => {
  const rows = [
    { key: 'L1', label: 'Ratio corriente', cells: [{ text: '1,2' }] },
    { key: 'L2', label: 'Prueba ácida', cells: [{ text: '0,8' }] },
  ];

  it('marca la fila de destino y sólo esa', () => {
    const { container } = render(<YearMatrix years={[2024]} rows={rows} highlightKey="L2" />);
    const marcadas = container.querySelectorAll('tr[aria-current="true"]');
    expect(marcadas.length).toBe(1);
    expect(marcadas[0]?.textContent).toContain('Prueba ácida');
  });

  it('sin destino no marca ninguna', () => {
    const { container } = render(<YearMatrix years={[2024]} rows={rows} />);
    expect(container.querySelectorAll('tr[aria-current="true"]').length).toBe(0);
  });

  it('un destino que no existe en esta tabla no marca nada ni revienta', () => {
    // Pasa de verdad: se enlaza D2 desde el veredicto de una empresa que no
    // reparte, y la fila no está.
    const { container } = render(<YearMatrix years={[2024]} rows={rows} highlightKey="D2" />);
    expect(container.querySelectorAll('tr[aria-current="true"]').length).toBe(0);
  });
});

/*
 * PHASE-44.24.D — la columna de tendencia.
 *
 * El informe pintaba el NIVEL de cada año y no la dirección. La columna existe
 * si ALGUNA fila trae la clave `spark`; que exista obliga a mover la cabecera,
 * el relleno de las filas de grupo y los dos `colSpan` — y un `colSpan` corto
 * parte la tabla en dos sin que ningún test de contenido lo note.
 */
describe('YearMatrix · la columna de tendencia', () => {
  const SPARK = {
    points: [
      { x: 0, y: 0 },
      { x: 0.5, y: 0.5 },
      { x: 1, y: 1 },
    ],
    trend: 'up' as const,
    ariaLabel: 'serie 2024-2026: 1,00×; 1,20×; 1,40× — ascendente',
  };

  function conSerie(spark: (typeof SPARK) | null): MatrixRow {
    return { key: 'L1', label: 'Ratio corriente', help: DEF, cells: [{ text: '1,42' }], spark };
  }

  it('no existe si ninguna fila la trae', () => {
    const { container } = render(<YearMatrix years={[2026]} rows={[fila('L1', 'Ratio')]} />);
    expect(container.querySelectorAll('thead th')).toHaveLength(2);
  });

  it('la serie se lee en voz alta con su unidad y su tendencia', () => {
    // Un dibujo sin texto alternativo es un dato que sólo existe para quien
    // puede verlo: la etiqueta la compone `@crisol/ui`, la misma para las dos
    // apps.
    render(<YearMatrix years={[2026]} rows={[conSerie(SPARK)]} />);
    expect(screen.getByRole('img', { name: SPARK.ariaLabel })).toBeTruthy();
  });

  it('una serie corta se DICE, no se deja en blanco', () => {
    // Una celda vacía se lee como «no calculable», que es una afirmación sobre
    // los datos de la empresa y no sobre el mínimo de puntos de una línea.
    render(<YearMatrix years={[2026]} rows={[conSerie(null)]} />);
    expect(screen.getByText('serie corta')).toBeTruthy();
  });

  it('la fila de ayuda abierta cubre TODAS las columnas, tendencia incluida', () => {
    // Con un `colSpan` corto la fila de ayuda deja una celda suelta a la
    // derecha y la rejilla se parte, sin que ningún test de contenido lo note.
    const { container } = render(
      <YearMatrix years={[2024, 2025, 2026]} rows={[conSerie(SPARK)]} />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Qué es «Ratio corriente»' }));
    const ayuda = container.querySelector('td[colspan]');
    expect(ayuda?.getAttribute('colspan')).toBe('5'); // 3 años + concepto + tendencia
  });

  it('una cabecera de bloque cubre también la columna de tendencia', () => {
    const { container } = render(
      <YearMatrix
        years={[2024, 2025, 2026]}
        rows={[{ key: 'g', label: 'Liquidez', isGroup: true, cells: [] }, conSerie(SPARK)]}
      />,
    );
    const grupo = container.querySelector('th[scope="colgroup"]');
    expect(grupo?.getAttribute('colspan')).toBe('5');
  });
});
