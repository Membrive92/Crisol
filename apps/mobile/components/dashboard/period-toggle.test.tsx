// @types/jest expone los globals (describe/it/expect) — sin import.
import { fireEvent, render } from '@testing-library/react-native';

import { PeriodToggle } from './period-toggle';

/*
 * PHASE-47 — El toggle de período (móvil), después de que el ciclo dejara de
 * ser un preset.
 *
 * Aquí vivía `describe('el chip «Mi ciclo» sólo existe con ajuste')`: cinco
 * casos sobre cuándo se pintaba un cuarto chip y cuándo no. Ese chip ya no
 * existe. El día que el usuario declara en Ajustes no añade una opción al
 * toggle — REDEFINE qué significa «Mes», así que el toggle vuelve a ser «Mes /
 * Año / Rango» y este componente vuelve a ser tonto: pinta lo que le den.
 *
 * La guarda que aquellos tests protegían (no ofrecer el ciclo mientras el
 * perfil carga, porque el servidor devolvía 422) no se ha perdido: se mudó a
 * `userMonthIsCycle`, que es quien decide ahora si `month` corta por el ciclo,
 * y sigue guardando POR VERDAD por la misma razón — el campo llega AUSENTE
 * mientras `useMe()` carga y con un backend anterior a la columna.
 */

const OPTIONS = ['month', 'year', 'custom'] as const;

describe('PeriodToggle', () => {
  it('pinta exactamente las opciones que le pasan, sin añadir ni quitar', () => {
    const { getByText, queryByText } = render(
      <PeriodToggle value="month" onChange={jest.fn()} options={OPTIONS} />,
    );

    expect(getByText('Mes')).toBeTruthy();
    expect(getByText('Año')).toBeTruthy();
    expect(getByText('Rango')).toBeTruthy();
    // El chip del preset no puede volver por la puerta de atrás.
    expect(queryByText(/mi ciclo/i)).toBeNull();
  });

  it('por defecto ofrece sólo mes y año', () => {
    const { getByText, queryByText } = render(
      <PeriodToggle value="month" onChange={jest.fn()} />,
    );

    expect(getByText('Mes')).toBeTruthy();
    expect(getByText('Año')).toBeTruthy();
    expect(queryByText('Rango')).toBeNull();
  });

  it('emite la opción pulsada', () => {
    const onChange = jest.fn();
    const { getByText } = render(
      <PeriodToggle value="month" onChange={onChange} options={OPTIONS} />,
    );

    fireEvent.press(getByText('Año'));
    expect(onChange).toHaveBeenCalledWith('year');
  });
});
