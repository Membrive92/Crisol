import { Pressable, StyleSheet, Text, View } from 'react-native';

import type { PeriodKey } from '@crisol/types';
import {
  colors,
  fontSize,
  fontWeight,
  radius,
  spacing,
} from '@crisol/ui';

// PHASE-41 — se eliminó `quarter` (sin sentido para un particular). `custom`
// es el rango libre `from/to` que define el usuario.
// C0 — `PeriodKey` (con `cycle`) vive en `@crisol/types`: estaba declarado dos
// veces, una por app. Se reexporta aquí para no romper los imports existentes.
export type { PeriodKey };

export interface PeriodToggleProps {
  value: PeriodKey;
  onChange: (next: PeriodKey) => void;
  /** Opciones a mostrar; por defecto sin `custom` (opt-in del consumidor). */
  options?: readonly PeriodKey[];
}

const LABELS: Record<PeriodKey, string> = {
  month: 'Mes',
  year: 'Año',
  custom: 'Rango',
};

const DEFAULT_OPTIONS: readonly PeriodKey[] = ['month', 'year'];

/**
 * Segmented Mes/Año/Rango equivalente a `StitchPeriodToggle` en
 * web pero con `Pressable` nativo.
 *
 * C0 — Este módulo ya NO calcula rangos. Tenía un `rangeForPeriod` propio, en
 * hora LOCAL y siempre sobre «ahora» (sin ancla), mientras web usaba
 * `boundsForAnchor` en UTC con ancla: con un corte día-exacto por ciclo las dos
 * plataformas cortarían en instantes distintos. Toda la aritmética de período
 * —`boundsForAnchor`, `boundsForCustomRange` y la del ciclo— vive ahora en
 * `@crisol/services`, y el ancla la trae el llamante.
 */
export function PeriodToggle({
  value,
  onChange,
  options = DEFAULT_OPTIONS,
}: PeriodToggleProps) {
  /*
   * PHASE-47 — el toggle vuelve a ser tonto: pinta las opciones que le den.
   *
   * Aquí vivía un filtro que escondía el chip «Mi ciclo» cuando el usuario no
   * tenía día declarado, con la guarda POR VERDAD de la lección PHASE-47.E. El
   * chip ya no existe —el ciclo ES el período «Mes»—, pero la lección no se ha
   * ido de paseo: se MUDA a `userMonthIsCycle`, que es quien decide ahora si
   * `month` corta por el ciclo o por el mes natural, y que sigue guardando por
   * verdad porque el campo puede llegar AUSENTE mientras el perfil carga.
   */
  const visible = options;
  return (
    <View style={styles.row}>
      {visible.map((opt) => {
        const active = opt === value;
        return (
          <Pressable
            key={opt}
            onPress={() => onChange(opt)}
            style={[styles.option, active && styles.optionActive]}
          >
            <Text style={[styles.optionText, active && styles.optionTextActive]}>
              {LABELS[opt]}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    backgroundColor: colors.surfaceMuted,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 2,
    alignSelf: 'flex-start',
    marginBottom: spacing.md,
  },
  option: {
    paddingVertical: 6,
    paddingHorizontal: spacing.md,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: 'transparent',
  },
  optionActive: {
    backgroundColor: colors.surface,
    borderColor: colors.borderStrong,
  },
  optionText: {
    fontSize: fontSize.sm,
    fontWeight: fontWeight.semibold,
    color: colors.textMuted,
  },
  optionTextActive: {
    color: colors.text,
  },
});
