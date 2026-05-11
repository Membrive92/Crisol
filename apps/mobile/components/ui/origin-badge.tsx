import { StyleSheet, Text, View } from 'react-native';

import type { TransactionSource } from '@crisol/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';

const LABELS: Record<TransactionSource, string> = {
  manual: 'Manual',
  import: 'Importado',
  receipt: 'Ticket',
  expected: 'Esperada',
};

interface Palette {
  bg: string;
  fg: string;
}

function paletteFor(source: TransactionSource): Palette {
  switch (source) {
    case 'import':
      return { bg: colors.primarySoft, fg: colors.primary };
    case 'receipt':
      return { bg: colors.successSoft, fg: colors.success };
    case 'expected':
      return { bg: colors.warningSoft, fg: colors.warning };
    case 'manual':
    default:
      return { bg: colors.surfaceMuted, fg: colors.textMuted };
  }
}

export interface OriginBadgeProps {
  source: TransactionSource;
}

export function OriginBadge({ source }: OriginBadgeProps) {
  const palette = paletteFor(source);
  return (
    <View style={[styles.chip, { backgroundColor: palette.bg }]}>
      <Text style={[styles.text, { color: palette.fg }]} numberOfLines={1}>
        {LABELS[source]}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  chip: {
    alignSelf: 'flex-start',
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs / 2,
    borderRadius: radius.sm,
  },
  text: {
    fontSize: fontSize.xs,
    fontWeight: fontWeight.semibold,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
});
