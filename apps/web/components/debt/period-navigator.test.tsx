import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { PeriodNavigator } from './period-navigator';

/*
 * C3a — El navegador de período con el preset «Mi ciclo».
 *
 * El test que importa es el del CLAMP, y conviene explicar por qué:
 *
 * Cuando la página pide con `cycle=true`, el backend devuelve
 * `available_from`/`available_to` YA como anclas de ciclo (los bucketea la
 * misma expresión desplazada). Los helpers `clampCycleAnchor`/`canStepCycle*`
 * existen para TRADUCIR meses naturales a ciclos, y con D>1 retroceden un mes
 * —el ciclo que contiene el día 1 del primer mes con datos abre el mes
 * anterior—. Aplicarlos sobre unos bounds ya traducidos los traduce DOS VECES
 * y habilita por la izquierda un ciclo vacío: la flecha ◀ llevaría a un
 * período sin un solo movimiento.
 */

function renderNavigator(over: {
  range?: 'month' | 'year';
  anchor?: string;
  availableFrom?: string | null;
  availableTo?: string | null;
  cycleStartDay?: number;
  boundsAlreadyInCycles?: boolean;
}) {
  const onRangeChange = vi.fn();
  const onAnchorChange = vi.fn();
  render(
    <PeriodNavigator
      range={over.range ?? 'month'}
      onRangeChange={onRangeChange}
      anchor={over.anchor ?? '2026-03'}
      onAnchorChange={onAnchorChange}
      availableFrom={over.availableFrom ?? '2026-03'}
      availableTo={over.availableTo ?? '2026-08'}
      cycleStartDay={over.cycleStartDay}
      boundsAlreadyInCycles={over.boundsAlreadyInCycles ?? true}
    />,
  );
  return { onRangeChange, onAnchorChange };
}

describe('el chip «Mi ciclo» sólo existe con ajuste', () => {
  /*
   * PHASE-47 — aquí había tres casos sobre cuándo aparecía el chip «Mi ciclo»
   * y cuándo no. El chip ya no existe: el día que el usuario declara en
   * Ajustes no añade una opción al toggle, REDEFINE qué significa «Mes».
   *
   * La guarda que aquellos tests protegían —no ofrecer el ciclo mientras el
   * perfil carga, porque el servidor devolvía 422— no se ha perdido: vive en
   * `userMonthIsCycle`, que decide si `month` corta por el ciclo y sigue
   * guardando POR VERDAD, porque el campo llega AUSENTE mientras `useMe()`
   * carga y con un backend anterior a la columna.
   */
  it('el toggle ofrece Mes / Año, y ningún cuarto preset', () => {
    renderNavigator({ range: 'month', cycleStartDay: 14 });

    expect(screen.getByRole('button', { name: 'Mes' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Año' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: /mi ciclo/i })).toBeNull();
  });
});

describe('el clamp con bounds que YA son anclas de ciclo', () => {
  it('no habilita un ciclo extra vacío por la izquierda', () => {
    // `availableFrom` es el ancla del primer ciclo CON datos. Estando en él, no
    // hay ninguno anterior al que ir.
    renderNavigator({ anchor: '2026-03', availableFrom: '2026-03', cycleStartDay: 14 });

    const prev = screen.getByRole('button', { name: /anterior/i });
    expect(prev.hasAttribute('disabled')).toBe(true);
  });

  it('sí permite retroceder cuando hay un ciclo anterior con datos', () => {
    renderNavigator({ anchor: '2026-05', availableFrom: '2026-03', cycleStartDay: 14 });

    const prev = screen.getByRole('button', { name: /anterior/i });
    expect(prev.hasAttribute('disabled')).toBe(false);
  });

  it('no deja pasar del último ciclo con datos', () => {
    renderNavigator({ anchor: '2026-08', availableTo: '2026-08', cycleStartDay: 14 });

    const next = screen.getByRole('button', { name: /siguiente/i });
    expect(next.hasAttribute('disabled')).toBe(true);
  });
});

describe('las flechas saltan de ciclo en ciclo', () => {
  it('retroceder lleva al ciclo anterior, no a otro sitio', async () => {
    const { onAnchorChange } = renderNavigator({
      anchor: '2026-05',
      availableFrom: '2026-01',
      cycleStartDay: 14,
    });

    await userEvent.click(screen.getByRole('button', { name: /anterior/i }));

    expect(onAnchorChange).toHaveBeenCalledWith('2026-04');
  });

  it('el titular nombra el período por el mes que lo ABRE', () => {
    renderNavigator({ anchor: '2026-05', cycleStartDay: 14 });

    // Decisión del usuario: su mes se llama como siempre se ha llamado. Aquí
    // ponía «Ciclo del 14 may 2026» — vocabulario nuevo para un concepto que
    // él ya tenía nombrado. Que vaya del 14 de mayo al 13 de junio lo declaró
    // una vez en Ajustes; no hace falta recordárselo en cada pantalla.
    expect(screen.getByText('Mayo 2026')).toBeTruthy();
    expect(screen.queryByText(/ciclo del/i)).toBeNull();
  });
});

/*
 * La otra mitad de la regla del clamp, y la que ESCONDE datos si se equivoca.
 *
 * El navegador lo usan dos clases de pantalla: las que piden con `cycle=true`
 * (dashboard, análisis), cuyos bounds ya vienen bucketizados por el backend, y
 * la de Deuda, cuyo endpoint NO tiene ese parámetro y devuelve meses naturales.
 * Aplicar el clamp mensual a los segundos deja inalcanzable el ciclo que
 * CONTIENE el primer movimiento.
 */
describe('cuando los bounds son MESES NATURALES (el caso de Deuda)', () => {
  it('deja llegar al ciclo que contiene el primer movimiento', () => {
    // D=14 y el primer pago el 5 de marzo: el backend de deuda dice
    // `available_from='2026-03'` (el MES del movimiento), pero ese pago vive en
    // el ciclo que ABRE el 14 de febrero. Sin traducir los bounds, la flecha ◀
    // sale deshabilitada en marzo y ese movimiento no aparece en ninguna vista
    // de ciclo del módulo.
    renderNavigator({
      anchor: '2026-03',
      availableFrom: '2026-03',
      cycleStartDay: 14,
      boundsAlreadyInCycles: false,
    });

    const prev = screen.getByRole('button', { name: /anterior/i });
    expect(prev.hasAttribute('disabled')).toBe(false);
  });

  it('y con los bounds YA en ciclos, ese mismo caso no retrocede', () => {
    // El contrapunto: si no distinguiéramos, una de las dos pantallas estaría
    // mal por fuerza. Mismo ancla y mismos bounds, distinta unidad, distinta
    // respuesta — que es justo lo que la prop declara.
    renderNavigator({
      anchor: '2026-03',
      availableFrom: '2026-03',
      cycleStartDay: 14,
      boundsAlreadyInCycles: true,
    });

    const prev = screen.getByRole('button', { name: /anterior/i });
    expect(prev.hasAttribute('disabled')).toBe(true);
  });
});
