// @types/jest expone los globals (describe/it/expect) — sin import.
import { fireEvent, render } from '@testing-library/react-native';

import type { PeriodKey } from '@crisol/types';
import { periodLabel } from '@crisol/services';
import { CYCLE_PRESET_LABEL } from '@crisol/ui';

import { PeriodNavigator } from './period-navigator';

/*
 * C3a — El navegador de período de móvil con el preset «Mi ciclo».
 *
 * El test que importa es el del CLAMP, y conviene explicar por qué:
 *
 * Cuando la pantalla pide con `cycle=true`, el backend devuelve
 * `available_from`/`available_to` YA como anclas de ciclo (los bucketea la
 * misma expresión desplazada). Los helpers `clampCycleAnchor`/`canStepCycle*`
 * existen para TRADUCIR meses naturales a ciclos, y con D>1 retroceden un mes
 * —el ciclo que contiene el día 1 del primer mes con datos abre el mes
 * anterior—. Aplicarlos sobre unos bounds ya traducidos los traduce DOS VECES
 * y habilita por la izquierda un ciclo vacío: la flecha ◀ llevaría a un
 * período sin un solo movimiento.
 *
 * Es el mismo contrato que fija `apps/web/components/debt/period-navigator.test.tsx`,
 * con su test a cada lado: si una de las dos plataformas cambiara de clamp, la
 * otra seguiría en verde sola.
 */

function renderNavigator(over: {
  range?: PeriodKey;
  anchor?: string;
  boundsAlreadyInCycles?: boolean;
  availableFrom?: string | null;
  availableTo?: string | null;
  cycleStartDay?: number;
  allowCustom?: boolean;
  customFrom?: string | null;
  customTo?: string | null;
}) {
  const onRangeChange = jest.fn();
  const onAnchorChange = jest.fn();
  const onCustomRangeChange = jest.fn();
  const view = render(
    <PeriodNavigator
      range={over.range ?? 'month'}
      onRangeChange={onRangeChange}
      anchor={over.anchor ?? '2026-03'}
      onAnchorChange={onAnchorChange}
      availableFrom={over.availableFrom === undefined ? '2026-03' : over.availableFrom}
      availableTo={over.availableTo === undefined ? '2026-08' : over.availableTo}
      allowCustom={over.allowCustom ?? false}
      customFrom={over.customFrom ?? null}
      customTo={over.customTo ?? null}
      onCustomRangeChange={onCustomRangeChange}
      cycleStartDay={over.cycleStartDay}
      boundsAlreadyInCycles={over.boundsAlreadyInCycles ?? true}
    />,
  );
  return { ...view, onRangeChange, onAnchorChange, onCustomRangeChange };
}

describe('el toggle no ofrece un cuarto preset', () => {
  /*
   * PHASE-47 — aquí había tres casos sobre cuándo aparecía el chip «Mi ciclo».
   * El chip ya no existe: el día que el usuario declara en Ajustes REDEFINE
   * qué significa «Mes» en vez de añadir una opción.
   *
   * La guarda que aquellos casos protegían —no ofrecer el ciclo mientras el
   * perfil carga— vive ahora en `userMonthIsCycle`, y sigue guardando POR
   * VERDAD porque el campo llega AUSENTE mientras `useMe()` carga.
   */
  it('con ajuste, «Mes» ya es el mes del usuario y no hay chip aparte', () => {
    const { getByText, queryByText } = renderNavigator({ range: 'month', cycleStartDay: 14 });

    expect(getByText('Mes')).toBeTruthy();
    expect(queryByText(CYCLE_PRESET_LABEL)).toBeNull();
  });
});

describe('el clamp con bounds que YA son anclas de ciclo', () => {
  it('no habilita un ciclo extra vacío por la izquierda', () => {
    // `availableFrom` es el ancla del primer ciclo CON datos. Estando en él, no
    // hay ninguno anterior al que ir.
    const { getByLabelText } = renderNavigator({
      anchor: '2026-03',
      availableFrom: '2026-03',
      cycleStartDay: 14,
    });

    expect(getByLabelText('Período anterior')).toBeDisabled();
  });

  it('sí permite retroceder cuando hay un ciclo anterior con datos', () => {
    const { getByLabelText } = renderNavigator({
      anchor: '2026-05',
      availableFrom: '2026-03',
      cycleStartDay: 14,
    });

    expect(getByLabelText('Período anterior')).not.toBeDisabled();
  });

  it('no deja pasar del último ciclo con datos', () => {
    const { getByLabelText } = renderNavigator({
      anchor: '2026-08',
      availableTo: '2026-08',
      cycleStartDay: 14,
    });

    expect(getByLabelText('Período siguiente')).toBeDisabled();
  });
});

describe('las flechas saltan de ciclo en ciclo', () => {
  it('retroceder lleva al ciclo anterior, no a otro sitio', () => {
    const { getByLabelText, onAnchorChange } = renderNavigator({
      anchor: '2026-05',
      availableFrom: '2026-01',
      cycleStartDay: 14,
    });

    fireEvent.press(getByLabelText('Período anterior'));

    expect(onAnchorChange).toHaveBeenCalledWith('2026-04');
  });
});

describe('el ancla fuera de datos se re-acota sola', () => {
  it('un ancla posterior al último ciclo con datos se corrige al llegar los límites', () => {
    // Antes de C3a el navegador de móvil NO tenía este efecto: el ancla por
    // defecto es el mes en curso y podía quedarse fuera del rango con datos
    // hasta que el usuario navegara. Con meses naturales aterrizabas, como
    // mucho, en un mes flojo; con el ciclo pintas un período VACÍO.
    const { onAnchorChange } = renderNavigator({
      anchor: '2026-12',
      availableFrom: '2026-03',
      availableTo: '2026-08',
      cycleStartDay: 14,
    });

    expect(onAnchorChange).toHaveBeenCalledWith('2026-08');
  });

  it('un ancla dentro de datos no dispara nada (idempotente)', () => {
    const { onAnchorChange } = renderNavigator({
      anchor: '2026-05',
      availableFrom: '2026-03',
      availableTo: '2026-08',
      cycleStartDay: 14,
    });

    expect(onAnchorChange).not.toHaveBeenCalled();
  });

  it('el rango libre se recorta a los días CON DATOS', () => {
    // Rango fijo y PASADO a propósito: `dataMaxDayStr` lee el reloj (nunca
    // deja elegir días futuros), así que un rango que incluya «hoy» haría que
    // el resultado del test dependiera del día en que se ejecute
    // (bomba de relojería de [AUDIT-2026-08]).
    const { onCustomRangeChange } = renderNavigator({
      range: 'custom',
      allowCustom: true,
      availableFrom: '2025-03',
      availableTo: '2025-06',
      customFrom: '2025-01-01',
      customTo: '2025-12-31',
    });

    expect(onCustomRangeChange).toHaveBeenCalledWith('2025-03-01', '2025-06-30');
  });
});

describe('paridad con web: la etiqueta nombra el mes que ABRE el período', () => {
  it('el titular es el del mes, no un vocabulario aparte', () => {
    /*
     * PHASE-47 — este bloque afirmaba lo contrario: que el titular fuera
     * `cycleLabel(14, '2026-05')` («Ciclo del 14 may 2026») y NUNCA «Mayo
     * 2026». Es una decisión de producto que el usuario invirtió: su mes se
     * llama como siempre se ha llamado, y que vaya del 14 de mayo al 13 de
     * junio lo declaró una vez en Ajustes.
     *
     * Sigue siendo paridad con web: la misma función `periodLabel`, derivada
     * de la capa compartida y no escrita a mano (lección PHASE-44.13).
     */
    const { getByText, queryByText } = renderNavigator({ anchor: '2026-05', cycleStartDay: 14 });

    expect(getByText(periodLabel('month', '2026-05'))).toBeTruthy();
    expect(queryByText(/ciclo del/i)).toBeNull();
  });
});

/*
 * La otra mitad de la regla del clamp — y la que ESCONDE datos si se equivoca.
 *
 * El navegador lo usan dos clases de pantalla: las que piden con `cycle=true`
 * (sus bounds ya vienen bucketizados por el backend) y la de Deuda, cuyo
 * endpoint NO tiene ese parámetro y devuelve meses naturales. Por eso la unidad
 * la declara el consumidor en vez de deducirse del preset.
 */
describe('cuando los bounds son MESES NATURALES (el caso de Deuda)', () => {
  it('deja llegar al ciclo que contiene el primer movimiento', () => {
    // D=14 y el primer pago el 5 de marzo: deuda dice `available_from='2026-03'`
    // (el MES del movimiento), pero ese pago vive en el ciclo que ABRE el 14 de
    // febrero. Sin traducir, la flecha ◀ sale deshabilitada en marzo y ese
    // movimiento no aparece en ninguna vista de ciclo del módulo.
    const { getByLabelText } = renderNavigator({
      range: 'month',
      anchor: '2026-03',
      availableFrom: '2026-03',
      cycleStartDay: 14,
      boundsAlreadyInCycles: false,
    });

    expect(getByLabelText('Período anterior')).not.toBeDisabled();
  });

  it('y con los bounds YA en ciclos, ese mismo caso no retrocede', () => {
    const { getByLabelText } = renderNavigator({
      range: 'month',
      anchor: '2026-03',
      availableFrom: '2026-03',
      cycleStartDay: 14,
      boundsAlreadyInCycles: true,
    });

    expect(getByLabelText('Período anterior')).toBeDisabled();
  });
});
