import { fireEvent, render } from '@testing-library/react-native';

import type { MatrixRow } from '@crisol/ui';

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
});
