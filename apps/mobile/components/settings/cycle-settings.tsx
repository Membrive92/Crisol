import { useState } from 'react';
import { Pressable, StyleSheet, Switch, Text, View } from 'react-native';

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

import { CyclePreview } from './cycle-preview';

/**
 * C2 (móvil, decisión D4 del plan) — El ajuste «mi mes empieza el día D», con
 * su previsualización. Paridad de
 * `apps/web/components/settings/cycle-settings.tsx`.
 *
 * El día vive en el servidor (`users.cycle_start_day`), no en el dispositivo:
 * es un dato del usuario, no una preferencia de esta pantalla — por eso móvil y
 * web leen y escriben el MISMO valor con los mismos hooks
 * (`useMe`/`useUpdateMe`) en vez de tener cada uno su propio estado local.
 *
 * **Invariante que esta pantalla no puede romper**: presentación pura. Cambiar
 * el día no mueve un céntimo de ningún saldo, ni una cuota del cuadro de
 * amortización, ni el ancla de ningún extracto — sólo por dónde se corta cada
 * período. Está escrito en pantalla porque el usuario tiene todo el derecho a
 * temerse lo contrario.
 */

/**
 * Los días que el ajuste admite. 29–31 no se ofrecen: febrero obligaría a
 * clampar. La lista se DERIVA de los límites de `@crisol/services` —escribir un
 * 28 a mano aquí sería una segunda declaración del mismo rango, que es lo que
 * acaba divergiendo del validador.
 */
const DAY_OPTIONS: number[] = Array.from(
  { length: MAX_CYCLE_START_DAY - MIN_CYCLE_START_DAY + 1 },
  (_, i) => MIN_CYCLE_START_DAY + i,
);

/**
 * Día que se propone al desactivar el modo predeterminado, si no había ninguno
 * guardado. No es el 1 a propósito: el 1 ES el mes natural, así que apagar el
 * interruptor no cambiaría nada y parecería roto.
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
  const [infoOpen, setInfoOpen] = useState(false);
  const day: number | null = draft === undefined ? saved : draft;
  const dirty = day !== saved;
  const canSave = dirty && !update.isPending;

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
      <View style={styles.card}>
        <Text style={styles.placeholder}>Cargando…</Text>
      </View>
    );
  }

  if (me.isError) {
    return (
      <View style={styles.card}>
        <Text style={styles.error} accessibilityRole="alert">
          {formatApiError(me.error, 'No se pudo cargar tu perfil')}
        </Text>
      </View>
    );
  }

  return (
    <View>
      <View style={styles.card}>
        <Text style={styles.cardTitle}>Tu día de cobro</Text>
        <Text style={styles.paragraph}>
          Si cobras el 14, tu mes de verdad no va del 1 al 31: va de nómina a
          nómina. Dinos qué día empieza y eso pasa a ser tu mes en toda la app —
          el período «Mes», los gráficos y los filtros cortan por ahí, y dejan de
          partir tu nómina por la mitad.
        </Text>

        <Text style={styles.current}>
          {saved === null
            ? 'Ahora mismo estás en modo predeterminado: tu mes va del día 1 al último.'
            : `Ahora mismo tu mes empieza el día ${saved} y termina el ${
                saved === 1 ? 'último día' : saved - 1
              } del siguiente.`}
        </Text>

        {/*
          * El modo predeterminado es un interruptor y no una opción más de la
          * rejilla: «mes natural» no es un día de corte, es la ausencia de uno.
          * El icono de información DESPLIEGA el texto en vez de enseñarlo al
          * pasar por encima — en táctil no existe el hover, así que un tooltip
          * de hover aquí sería un texto que nadie puede leer (misma razón por
          * la que PHASE-44.15 sacó los motivos del `title` en el buscador).
          */}
        <View style={styles.defaultModeRow}>
          <Switch
            testID="cycle-default-mode"
            accessibilityLabel="Modo predeterminado"
            value={day === null}
            onValueChange={(on) => setDraft(on ? null : (saved ?? DEFAULT_SUGGESTED_DAY))}
            trackColor={{ false: colors.border, true: colors.primary }}
          />
          <Text style={styles.defaultModeLabel}>Modo predeterminado</Text>
          <Pressable
            testID="cycle-default-mode-info"
            accessibilityRole="button"
            accessibilityLabel="Qué es el modo predeterminado"
            onPress={() => setInfoOpen((v) => !v)}
            hitSlop={10}
            style={styles.infoBadge}
          >
            <Text style={styles.infoBadgeText}>i</Text>
          </Pressable>
        </View>
        {infoOpen ? (
          <Text testID="cycle-default-mode-help" style={styles.infoText}>
            El modo predeterminado coge el periodo de un mes natural: del día 1
            al último. Desactívalo para que tu mes empiece el día que tú cobras.
          </Text>
        ) : null}

        {day === null ? null : (
          <Text style={styles.fieldLabel}>El día en que empieza tu mes</Text>
        )}
        <View style={day === null ? styles.hidden : styles.dayGrid}>
          {DAY_OPTIONS.map((d) => (
            <Pressable
              key={d}
              testID="cycle-day-option"
              accessibilityRole="button"
              accessibilityLabel={`Día ${d}`}
              accessibilityState={{ selected: day === d }}
              onPress={() => setDraft(d)}
              style={[styles.dayOption, day === d && styles.optionSelected]}
            >
              <Text style={[styles.dayOptionText, day === d && styles.optionTextSelected]}>
                {d}
              </Text>
            </Pressable>
          ))}
        </View>

        <Pressable
          testID="cycle-save"
          accessibilityRole="button"
          accessibilityState={{ disabled: !canSave }}
          disabled={!canSave}
          onPress={handleSave}
          style={({ pressed }) => [
            styles.saveButton,
            !canSave && styles.saveButtonDisabled,
            pressed && canSave && { opacity: 0.85 },
          ]}
        >
          <Text style={styles.saveButtonText}>
            {update.isPending ? 'Guardando…' : 'Guardar'}
          </Text>
        </Pressable>
        {dirty ? (
          <Text style={styles.dirtyHint}>Sin guardar. Lo de abajo es una previsualización.</Text>
        ) : null}
      </View>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>Cómo quedaría el corte</Text>
        <View style={styles.previewSlot}>
          {day === null ? (
            <Text style={styles.paragraph}>
              Con el mes natural no hay nada que previsualizar: cada período va
              del día 1 al último, como hasta ahora. Elige un día arriba para ver
              qué movimientos caen a cada lado del corte.
            </Text>
          ) : (
            <CyclePreview cycleStartDay={day} />
          )}
        </View>
      </View>

      <ChangeWarning />
    </View>
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
    <View style={styles.warning}>
      <Text style={styles.warningTitle}>Antes de guardar</Text>
      <WarningItem>
        Se vuelve a cortar todo tu histórico, no sólo el mes en curso: cada
        período pasa a ir de tu día de cobro al día anterior del mes siguiente.
      </WarningItem>
      <WarningItem>
        Las comparativas «vs período anterior» cambian de base, así que sus
        porcentajes no van a coincidir con los que ves hoy.
      </WarningItem>
      <WarningItem>
        No se mueve ni un céntimo. Tus saldos, tus importes, tu deuda y tus
        extractos son exactamente los mismos: lo único que cambia es por dónde se
        corta cada período.
      </WarningItem>
      <WarningItem>Puedes volver al mes natural cuando quieras, y nada se pierde.</WarningItem>
    </View>
  );
}

function WarningItem({ children }: { children: string }) {
  return (
    <View style={styles.warningItem}>
      <Text style={styles.warningBullet}>•</Text>
      <Text style={styles.warningText}>{children}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  cardTitle: {
    fontSize: fontSize.md,
    fontWeight: fontWeight.semibold,
    color: colors.text,
    marginBottom: spacing.sm,
  },
  paragraph: {
    fontSize: fontSize.sm,
    color: colors.textMuted,
    lineHeight: 18,
    marginBottom: spacing.sm,
  },
  current: {
    fontSize: fontSize.sm,
    color: colors.text,
    marginBottom: spacing.md,
  },
  fieldLabel: {
    fontSize: fontSize.xs,
    fontWeight: fontWeight.semibold,
    color: colors.textMuted,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
    marginBottom: spacing.sm,
  },
  naturalOption: {
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surfaceMuted,
    marginBottom: spacing.sm,
  },
  naturalOptionText: { fontSize: fontSize.sm, color: colors.text },
  dayGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.xs,
    marginBottom: spacing.md,
  },
  dayOption: {
    minWidth: 42,
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.sm,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surfaceMuted,
    alignItems: 'center',
  },
  dayOptionText: { fontSize: fontSize.sm, color: colors.text },
  defaultModeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginTop: spacing.sm,
    marginBottom: spacing.sm,
  },
  defaultModeLabel: { color: colors.text, fontSize: fontSize.sm, fontWeight: fontWeight.medium },
  infoBadge: {
    width: 18,
    height: 18,
    borderRadius: 9,
    borderWidth: 1,
    borderColor: colors.textMuted,
    alignItems: 'center',
    justifyContent: 'center',
  },
  infoBadgeText: { color: colors.textMuted, fontSize: 11, fontWeight: fontWeight.semibold },
  infoText: {
    color: colors.textMuted,
    fontSize: fontSize.xs,
    lineHeight: 18,
    marginBottom: spacing.sm,
  },
  hidden: { display: 'none' },
  optionSelected: { backgroundColor: colors.primary, borderColor: colors.primary },
  optionTextSelected: { color: colors.onPrimary, fontWeight: fontWeight.semibold },
  saveButton: {
    alignSelf: 'flex-start',
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.lg,
    borderRadius: radius.sm,
    backgroundColor: colors.primary,
  },
  saveButtonDisabled: { opacity: 0.5 },
  saveButtonText: { color: colors.onPrimary, fontWeight: fontWeight.semibold },
  dirtyHint: { marginTop: spacing.sm, fontSize: fontSize.xs, color: colors.textMuted },
  previewSlot: { marginTop: spacing.xs },
  placeholder: { fontSize: fontSize.sm, color: colors.textMuted },
  error: { fontSize: fontSize.sm, color: colors.danger },
  warning: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.surfaceMuted,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  warningTitle: {
    fontSize: fontSize.sm,
    fontWeight: fontWeight.semibold,
    color: colors.text,
    marginBottom: spacing.sm,
  },
  warningItem: { flexDirection: 'row', gap: spacing.xs, marginBottom: spacing.xs },
  warningBullet: { fontSize: fontSize.sm, color: colors.textMuted, lineHeight: 18 },
  warningText: { flex: 1, fontSize: fontSize.sm, color: colors.textMuted, lineHeight: 18 },
});
