import { fireEvent, render } from '@testing-library/react-native';

import type { MatrixRow } from '@crisol/ui';

import { StyleSheet } from 'react-native';

import { colors } from '@crisol/ui';

import { YearMatrix } from './year-matrix';

/**
 * `MatrixCell.title` lleva el porqué de un hueco, de una aproximación o de una
 * vara que no aplica. En web sale como `title=`; en táctil eso no existe, así
 * que en móvil **no se pintaba nunca** y el motivo por celda se perdía entero.
 *
 * Importa cuando una métrica falla por razones distintas en años distintos: el
 * motivo de la fila sólo puede contar uno (el del ejercicio más reciente, regla
 * 8 de honestidad), y el resto sólo vive en la celda.
 */

const rows: MatrixRow[] = [
  {
    key: 'm_score',
    label: 'M-Score de Beneish',
    hint: "falta la partida 'cogs'",
    cells: [
      { text: '—', title: 'no hay ejercicio anterior con el que comparar' },
      { text: '—', title: "falta la partida 'cogs'" },
    ],
  },
];

describe('YearMatrix (móvil)', () => {
  it('el motivo de una celda se lee al pulsarla', () => {
    const { getAllByText, getByText, queryByText } = render(
      <YearMatrix years={[2023, 2024]} rows={rows} />,
    );

    expect(queryByText(/no hay ejercicio anterior/)).toBeNull();
    fireEvent.press(getAllByText(/—/)[0]!);
    expect(getByText(/no hay ejercicio anterior/)).toBeTruthy();
    expect(getByText(/M-Score de Beneish · 2023/)).toBeTruthy();
  });

  it('cada ejercicio enseña SU motivo, no el de la fila', () => {
    // El caso de McDonald's: el primer año falla por no tener anterior y el
    // resto porque la empresa no publica coste de ventas.
    const { getAllByText, getByText } = render(<YearMatrix years={[2023, 2024]} rows={rows} />);

    fireEvent.press(getAllByText(/—/)[1]!);
    expect(getByText(/M-Score de Beneish · 2024/)).toBeTruthy();
    // Dos apariciones: la de la fila (el motivo del ejercicio más reciente) y
    // la del detalle de ESTA celda, que es la que se acaba de pulsar.
    expect(getAllByText(/falta la partida 'cogs'/)).toHaveLength(2);
  });

  it('volver a pulsar la misma celda cierra el detalle', () => {
    const { getAllByText, queryByText } = render(<YearMatrix years={[2023, 2024]} rows={rows} />);

    fireEvent.press(getAllByText(/—/)[0]!);
    fireEvent.press(getAllByText(/—/)[0]!);
    expect(queryByText(/no hay ejercicio anterior/)).toBeNull();
  });

  it('una celda sin motivo no es pulsable ni promete nada', () => {
    const sinMotivo: MatrixRow[] = [
      { key: 'L1', label: 'Ratio corriente', cells: [{ text: '2,0' }] },
    ];
    const { getByText, queryByText } = render(<YearMatrix years={[2024]} rows={sinMotivo} />);

    fireEvent.press(getByText(/2,0/));
    expect(queryByText(/Ratio corriente · 2024/)).toBeNull();
  });

  /*
   * PHASE-44.23 — la definición de la FILA («qué es esta métrica»), que se abre
   * tocando la etiqueta. Comparte panel con el motivo de la celda a propósito:
   * en una pantalla de móvil no caben dos sitios donde mirar.
   */
  it('la definición de la fila se lee al tocar su etiqueta', () => {
    const conAyuda: MatrixRow[] = [
      { ...rows[0]!, help: 'Modelo de Beneish: indicios de maquillaje contable.' },
    ];
    const { getByText, queryByText } = render(<YearMatrix years={[2025, 2026]} rows={conAyuda} />);

    expect(queryByText('Modelo de Beneish: indicios de maquillaje contable.')).toBeNull();
    fireEvent.press(getByText('M-Score de Beneish ⓘ'));
    expect(getByText('Modelo de Beneish: indicios de maquillaje contable.')).toBeTruthy();
  });

  it('volver a tocar la etiqueta cierra la definición', () => {
    // El mismo gesto la abre y la cierra: sin esto, el panel se queda abierto y
    // hay que buscar otra fila que pulsar para quitarlo de en medio.
    const conAyuda: MatrixRow[] = [{ ...rows[0]!, help: 'Modelo de Beneish.' }];
    const { getByText, queryByText } = render(<YearMatrix years={[2025, 2026]} rows={conAyuda} />);

    fireEvent.press(getByText('M-Score de Beneish ⓘ'));
    expect(getByText('Modelo de Beneish.')).toBeTruthy();
    fireEvent.press(getByText('M-Score de Beneish ⓘ'));
    expect(queryByText('Modelo de Beneish.')).toBeNull();
  });

  it('una fila sin definición no ofrece la ⓘ ni es pulsable', () => {
    // Un ⓘ que abre un panel vacío es peor que no tener ⓘ.
    const { getByText, queryByText } = render(<YearMatrix years={[2025, 2026]} rows={rows} />);
    expect(queryByText('M-Score de Beneish ⓘ')).toBeNull();
    expect(getByText('M-Score de Beneish')).toBeTruthy();
  });

  it('abrir la definición cierra el motivo de una celda, y al revés', () => {
    // Es el mismo panel: si los dos pudieran estar abiertos, el segundo pisaría
    // al primero sin que se notara cuál se está leyendo.
    const conAyuda: MatrixRow[] = [{ ...rows[0]!, help: 'Modelo de Beneish.' }];
    const { getByText, queryByText, getAllByText } = render(
      <YearMatrix years={[2025, 2026]} rows={conAyuda} />,
    );

    fireEvent.press(getAllByText(/—/)[0]!);
    expect(getByText('no hay ejercicio anterior con el que comparar')).toBeTruthy();

    fireEvent.press(getByText('M-Score de Beneish ⓘ'));
    expect(getByText('Modelo de Beneish.')).toBeTruthy();
    expect(queryByText('no hay ejercicio anterior con el que comparar')).toBeNull();
  });
});

/**
 * La fila a la que se llega desde una señal se ve (PHASE-44.24, auditoría UX).
 *
 * Se comprueba el estilo APLICADO al texto de la etiqueta, no la prop: un
 * `highlightKey` que llega y no pinta nada es exactamente el defecto.
 */
describe('YearMatrix (móvil): la fila resaltada', () => {
  const dos: MatrixRow[] = [
    { key: 'L1', label: 'Ratio corriente', cells: [{ text: '1,4' }, { text: '1,5' }] },
    { key: 'L2', label: 'Prueba ácida', cells: [{ text: '0,9' }, { text: '1,0' }] },
  ];

  it('marca sólo la fila de destino', () => {
    const { getByText } = render(<YearMatrix years={[2024, 2025]} rows={dos} highlightKey="L2" />);
    const marcada = StyleSheet.flatten(getByText('Prueba ácida').props.style);
    const otra = StyleSheet.flatten(getByText('Ratio corriente').props.style);
    expect(marcada.color).toBe(colors.primary);
    expect(otra.color).not.toBe(colors.primary);
  });

  it('sin destino no marca ninguna', () => {
    const { getByText } = render(<YearMatrix years={[2024, 2025]} rows={dos} />);
    expect(StyleSheet.flatten(getByText('Prueba ácida').props.style).color).not.toBe(
      colors.primary,
    );
  });
});
