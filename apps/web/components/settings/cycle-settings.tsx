'use client';

import { useState } from 'react';

import {
  MAX_CYCLE_START_DAY,
  MIN_CYCLE_START_DAY,
  formatApiError,
  isValidCycleStartDay,
  useMe,
  useUpdateMe,
} from '@crisol/services';
import { toast, useAuthStore } from '@crisol/store';
import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';

import { Button } from '@/components/ui/button';
import { Card, CardTitle } from '@/components/ui/card';
import { Select } from '@/components/ui/field';
import { InfoTooltip } from '@/components/ui/info-tooltip';

import { CyclePreview } from './cycle-preview';

/**
 * C2 — El ajuste «mi mes empieza el día D», con su previsualización.
 *
 * El día vive en el servidor (`users.cycle_start_day`), no en el dispositivo:
 * es un dato del usuario, no una preferencia de esta pantalla. Es la primera
 * preferencia de perfil del sistema, así que estrena `useMe`/`useUpdateMe`.
 *
 * **Invariante que esta pantalla no puede romper**: presentación pura. Cambiar
 * el día no mueve un céntimo de ningún saldo, ni una cuota del cuadro de
 * amortización, ni el ancla de ningún extracto — sólo por dónde se corta cada
 * período. Está escrito en pantalla porque el usuario tiene todo el derecho a
 * temerse lo contrario.
 */

/** Los días que el ajuste admite. 29–31 no se ofrecen: febrero obligaría a clampar. */
const DAY_OPTIONS: number[] = Array.from(
  { length: MAX_CYCLE_START_DAY - MIN_CYCLE_START_DAY + 1 },
  (_, i) => MIN_CYCLE_START_DAY + i,
);

/**
 * Día que se propone al desmarcar el modo predeterminado, si el usuario no
 * tenía ninguno guardado. No es «el día 1» a propósito: el 1 equivale al mes
 * natural, así que desmarcar el check no cambiaría nada y parecería roto.
 */
const DEFAULT_SUGGESTED_DAY = 15;

export function CycleSettings() {
  const me = useMe();
  const update = useUpdateMe();

  /*
   * Guarda por VERDAD, no por `!== null` (lección PHASE-47.E).
   *
   * Mientras exista un backend en marcha anterior a la columna, la clave llega
   * AUSENTE — y `undefined !== null` es cierto, así que la comparación estricta
   * daría por configurado a TODO el mundo. `isValidCycleStartDay` cierra por la
   * misma puerta el `undefined`, el `null`, el 0, el 29 y un `'14'` que llegara
   * como cadena desde una respuesta antigua.
   */
  const savedRaw = me.data?.cycle_start_day;
  const saved: number | null = isValidCycleStartDay(savedRaw) ? savedRaw : null;

  /*
   * `undefined` = «el usuario no ha tocado nada», y por eso el estado tiene
   * tres valores y no dos: con dos, un refetch del perfil pisaría la elección
   * en curso (o, al revés, el valor guardado nunca aparecería en el selector).
   */
  const [draft, setDraft] = useState<number | null | undefined>(undefined);
  const day: number | null = draft === undefined ? saved : draft;
  const dirty = day !== saved;

  function handleSave() {
    update.mutate(
      { cycle_start_day: day },
      {
        onSuccess: (updated) => {
          // El hook invalida `auth.me`; sincronizar el STORE es cosa del
          // llamante porque `@crisol/services` no puede importar
          // `@crisol/store` (regla de imports de architecture.md,
          // AUDIT-2026-05). Media app lee el usuario de aquí: sin esta línea,
          // esas pantallas se quedarían con el valor viejo hasta el próximo
          // login.
          useAuthStore.getState().setUser(updated);
          // Volvemos a seguir al servidor: el borrador ya no aporta nada y
          // dejarlo puesto haría que la pantalla mintiera si otro dispositivo
          // cambia el ajuste.
          setDraft(undefined);
          toast.success(
            updated.cycle_start_day
              ? `Listo: tu mes empieza el día ${updated.cycle_start_day}.`
              : 'Listo: vuelves al mes natural, del 1 al último día.',
          );
        },
        onError: (err) => toast.error(formatApiError(err, 'No se pudo guardar el ajuste')),
      },
    );
  }

  if (me.isLoading) {
    return (
      <Card>
        <p style={{ margin: 0, color: colors.textMuted, fontSize: fontSize.sm }}>Cargando…</p>
      </Card>
    );
  }

  if (me.isError) {
    return (
      <Card>
        <p role="alert" style={{ margin: 0, color: colors.danger, fontSize: fontSize.sm }}>
          {formatApiError(me.error, 'No se pudo cargar tu perfil')}
        </p>
      </Card>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.lg }}>
      <Card>
        <CardTitle>Tu día de cobro</CardTitle>
        <p
          style={{
            margin: `${spacing.sm}px 0 ${spacing.md}px 0`,
            fontSize: fontSize.sm,
            color: colors.textMuted,
            lineHeight: 1.5,
          }}
        >
          Si cobras el 14, tu mes de verdad no va del 1 al 31: va de nómina a
          nómina. Dinos qué día empieza y <strong>eso pasa a ser tu mes</strong>{' '}
          en toda la app — el período «Mes», los gráficos y los filtros cortan
          por ahí, y dejan de partir tu nómina por la mitad.
        </p>

        <p
          style={{
            margin: `0 0 ${spacing.md}px 0`,
            fontSize: fontSize.sm,
            color: colors.text,
          }}
        >
          {saved === null
            ? 'Ahora mismo estás en modo predeterminado: tu mes va del día 1 al último.'
            : `Ahora mismo tu mes empieza el día ${saved} y termina el ${saved === 1 ? 'último día' : `${saved - 1}`} del siguiente.`}
        </p>

        {/*
          * El modo predeterminado es un CHECK y no una opción más del
          * desplegable: «mes natural» no es un día de corte, es la ausencia de
          * uno. Mezclarlos en la misma lista obligaba a leer trece entradas
          * para descubrir que la primera era de otra naturaleza.
          */}
        <label
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: spacing.sm,
            fontSize: fontSize.sm,
            color: colors.text,
            cursor: 'pointer',
            userSelect: 'none',
          }}
        >
          <input
            type="checkbox"
            checked={day === null}
            onChange={(e) => setDraft(e.target.checked ? null : (saved ?? DEFAULT_SUGGESTED_DAY))}
            style={{ width: 16, height: 16, accentColor: colors.primary, cursor: 'pointer' }}
          />
          <span style={{ fontWeight: fontWeight.medium }}>Modo predeterminado</span>
          <InfoTooltip
            text="El modo predeterminado coge el periodo de un mes natural: del día 1 al último. Desmárcalo para que tu mes empiece el día que tú cobras."
            label="Qué es el modo predeterminado"
          />
        </label>

        {day === null ? null : (
          <div style={{ maxWidth: 320, marginTop: spacing.md }}>
            <Select
              label="El día en que empieza tu mes"
              value={String(day)}
              onChange={(e) => setDraft(Number(e.target.value))}
            >
              {DAY_OPTIONS.map((d) => (
                <option key={d} value={d}>
                  Día {d}
                </option>
              ))}
            </Select>
          </div>
        )}

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: spacing.md,
            marginTop: spacing.sm,
          }}
        >
          <Button type="button" onClick={handleSave} disabled={!dirty || update.isPending}>
            {update.isPending ? 'Guardando…' : 'Guardar'}
          </Button>
          {dirty ? (
            <span style={{ fontSize: fontSize.xs, color: colors.textMuted }}>
              Sin guardar. Lo de abajo es una previsualización.
            </span>
          ) : null}
        </div>
      </Card>

      <Card>
        <CardTitle>Cómo quedaría el corte</CardTitle>
        <div style={{ marginTop: spacing.md }}>
          {day === null ? (
            <p style={{ margin: 0, fontSize: fontSize.sm, color: colors.textMuted, lineHeight: 1.5 }}>
              Con el mes natural no hay nada que previsualizar: cada período va
              del día 1 al último, como hasta ahora. Elige un día arriba para ver
              qué movimientos caen a cada lado del corte.
            </p>
          ) : (
            <CyclePreview cycleStartDay={day} />
          )}
        </div>
      </Card>

      <ChangeWarning />
    </div>
  );
}

/**
 * Lo que cambia al cambiar el día (decisión D2 del plan: se re-corta TODO el
 * histórico) y lo que NO cambia. Las dos mitades hacen falta: sin la primera el
 * usuario se sorprende al ver moverse meses de hace un año; sin la segunda, se
 * teme que le hayan tocado los saldos.
 */
function ChangeWarning() {
  return (
    <div
      style={{
        border: `1px solid ${colors.border}`,
        borderRadius: radius.md,
        padding: spacing.md,
        backgroundColor: colors.surfaceMuted,
      }}
    >
      <h3
        style={{
          margin: 0,
          fontSize: fontSize.sm,
          fontWeight: fontWeight.semibold,
          color: colors.text,
        }}
      >
        Antes de guardar
      </h3>
      <ul
        style={{
          margin: `${spacing.sm}px 0 0 0`,
          paddingLeft: spacing.lg,
          fontSize: fontSize.sm,
          color: colors.textMuted,
          lineHeight: 1.6,
        }}
      >
        <li>
          Se vuelve a cortar <strong>todo tu histórico</strong>, no sólo el mes en
          curso: cada período pasa a ir de tu día de cobro al día anterior del mes
          siguiente.
        </li>
        <li>
          Las comparativas «vs período anterior» cambian de base, así que sus
          porcentajes no van a coincidir con los que ves hoy.
        </li>
        <li>
          <strong>No se mueve ni un céntimo.</strong> Tus saldos, tus importes, tu
          deuda y tus extractos son exactamente los mismos: lo único que cambia es
          por dónde se corta cada período.
        </li>
        <li>Puedes volver al mes natural cuando quieras, y nada se pierde.</li>
      </ul>
    </div>
  );
}
