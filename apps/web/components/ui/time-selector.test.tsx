import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { TimeSelector, isCycleRange } from './time-selector';

/*
 * C3b — El TimeSelector con el ciclo del usuario.
 *
 * Este componente lo usan la lista de transacciones y el drill-down de
 * categoría, que NO son pantallas de esta feature. Por eso lo primero que se
 * prueba aquí no es el ciclo: es que sin el ajuste todo siga exactamente igual.
 * Un usuario que no ha configurado nada no puede notar que esto existe.
 */

const periods = [{ year: 2026, months: [7, 8, 9] }];

function renderSelector(props: {
  cycleStartDay?: number;
  dateFrom?: string;
  dateTo?: string;
}) {
  const onChange = vi.fn();
  render(
    <TimeSelector
      availablePeriods={periods}
      value={{ dateFrom: props.dateFrom, dateTo: props.dateTo }}
      onChange={onChange}
      cycleStartDay={props.cycleStartDay}
    />,
  );
  return onChange;
}

describe('TimeSelector sin ajuste de ciclo: nada cambia', () => {
  it('no ofrece el chip «Mi ciclo»', () => {
    renderSelector({});

    expect(screen.queryByRole('button', { name: /mi ciclo/i })).toBeNull();
  });

  it('elegir un mes sigue emitiendo el mes NATURAL completo', async () => {
    const onChange = renderSelector({});

    // El nombre accesible dice el mes y el año, sin más: en modo natural un
    // chip es exactamente el mes que pone.
    await userEvent.click(screen.getByRole('button', { name: 'Ago 2026' }));

    expect(onChange).toHaveBeenCalledWith({
      dateFrom: '2026-08-01T00:00:00.000Z',
      dateTo: '2026-08-31T23:59:59.000Z',
    });
  });

  it('un campo AUSENTE no activa el preset', () => {
    // El perfil llega sin la clave mientras carga `useMe()`, y también si el
    // backend en marcha es anterior a la columna. La prop se escribe OMITIDA,
    // no a `null`: con `null` el test pasaría igual y no probaría nada
    // (lección PHASE-47.E).
    const props: { cycleStartDay?: number } = {};
    renderSelector(props);

    // Sin día declarado, un mes es el natural y ningún chip promete otra cosa.
    expect(screen.queryByRole('button', { name: /ciclo del/i })).toBeNull();
  });
});

describe('TimeSelector con ajuste de ciclo', () => {
  it('sin chip que pulsar, un mes YA significa su ciclo', async () => {
    const onChange = renderSelector({ cycleStartDay: 14 });

    /*
     * PHASE-47 — aquí se pulsaba primero un chip «Mi ciclo». Ya no existe: el
     * usuario respondió esa pregunta una vez en Ajustes y no tiene que
     * repetirla en cada pantalla. Lo que el test protege sigue siendo lo
     * mismo, y ahora vale desde el primer render.
     *
     * El chip del mes se ANUNCIA por lo que realmente elige, no como «Ago»:
     * quien navegue con lector de pantalla no puede quedarse con que está
     * eligiendo agosto cuando elige del 14 de agosto al 13 de septiembre.
     */
    await userEvent.click(screen.getByRole('button', { name: 'Ciclo del 14 ago 2026' }));

    // «Ago» ya no es del 1 al 31: es el mes del usuario, que ABRE en agosto.
    expect(onChange).toHaveBeenCalledWith({
      dateFrom: '2026-08-14T00:00:00.000Z',
      dateTo: '2026-09-13T23:59:59.000Z',
    });
  });

  it('describe el ciclo por su día de cobro, no como «rango personalizado»', () => {
    // Es el defecto que este entregable existía para arreglar: el componente
    // deduce el modo del RANGO (`isFullMonth`/`isFullYear`), y un 14-ago →
    // 13-sep no casa ninguno de los dos, así que caía al literal de rango libre
    // y el usuario veía su propio mes descrito como una rareza.
    renderSelector({
      cycleStartDay: 14,
      dateFrom: '2026-08-14T00:00:00.000Z',
      dateTo: '2026-09-13T23:59:59.000Z',
    });

    expect(screen.getByText(/Ciclo del 14 ago 2026/)).toBeTruthy();
    expect(screen.queryByText(/rango personalizado/i)).toBeNull();
  });
});

describe('isCycleRange', () => {
  const from = '2026-08-14T00:00:00.000Z';
  const to = '2026-09-13T23:59:59.000Z';

  it('reconoce el ciclo sólo cuando recibe el día', () => {
    expect(isCycleRange(from, to, 14)).toBe(true);
    // Sin el día no hay nada que reconocer: el mismo rango es un rango libre.
    expect(isCycleRange(from, to, undefined)).toBe(false);
    // Y con OTRO día tampoco: el rango del 14 no es el ciclo del 20.
    expect(isCycleRange(from, to, 20)).toBe(false);
  });

  it('no confunde un rango libre cualquiera con un ciclo', () => {
    expect(isCycleRange('2026-08-03T00:00:00.000Z', '2026-08-27T23:59:59.000Z', 14)).toBe(
      false,
    );
  });

  it('con D=1 el rango ES un mes natural, y así se sigue llamando', () => {
    // Con el día 1 el ciclo degenera en el mes natural, así que el rango casa
    // las DOS descripciones. Gana la de siempre: llamar «Ciclo del 1 ago» a lo
    // que el usuario pidió como «Agosto» sería inventarle una rareza.
    const enero = { dateFrom: '2026-08-01T00:00:00.000Z', dateTo: '2026-08-31T23:59:59.000Z' };
    expect(isCycleRange(enero.dateFrom, enero.dateTo, 1)).toBe(true);

    renderSelector({ cycleStartDay: 1, ...enero });
    expect(screen.getByText(/Agosto 2026/)).toBeTruthy();
    expect(screen.queryByText(/Ciclo del 1 ago/)).toBeNull();
  });
});
