import { StyleSheet, Text, View } from 'react-native';

import type { CategoryKind } from '@finanzas/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@finanzas/ui';

export interface CategoryChipProps {
  label: string;
  kind: CategoryKind | null;
}

interface Palette {
  bg: string;
  fg: string;
}

function paletteFor(kind: CategoryKind | null): Palette {
  if (kind === 'income') return { bg: colors.successSoft, fg: colors.success };
  if (kind === 'expense') return { bg: colors.dangerSoft, fg: colors.danger };
  return { bg: colors.primarySoft, fg: colors.primary };
}

export function CategoryChip({ label, kind }: CategoryChipProps) {
  const palette = paletteFor(kind);
  return (
    <View style={[styles.chip, { backgroundColor: palette.bg }]}>
      <Text style={[styles.text, { color: palette.fg }]} numberOfLines={1}>
        {label}
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
