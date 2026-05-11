import { StyleSheet, Text, View } from 'react-native';

import type { CategoryKind } from '@crisol/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';

export interface CategoryChipProps {
  label: string;
  kind: CategoryKind | null;
  /** Hex `#RRGGBB` propio de la categoría — gana sobre la paleta por kind. */
  color?: string | null;
  /** Emoji prefix opcional. */
  icon?: string | null;
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

function hexToRgba(hex: string, alpha: number): string | null {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex.trim());
  if (!m) return null;
  const v = m[1]!;
  const r = parseInt(v.slice(0, 2), 16);
  const g = parseInt(v.slice(2, 4), 16);
  const b = parseInt(v.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function paletteForColor(color: string): Palette {
  const bg = hexToRgba(color, 0.15);
  if (bg === null) return paletteFor(null);
  return { bg, fg: color };
}

export function CategoryChip({ label, kind, color, icon }: CategoryChipProps) {
  const palette = color ? paletteForColor(color) : paletteFor(kind);
  return (
    <View style={[styles.chip, { backgroundColor: palette.bg }]}>
      {icon ? (
        <Text style={styles.icon} accessibilityElementsHidden>
          {icon}
        </Text>
      ) : null}
      <Text style={[styles.text, { color: palette.fg }]} numberOfLines={1}>
        {label}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  chip: {
    alignSelf: 'flex-start',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
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
  icon: { fontSize: fontSize.sm },
});
