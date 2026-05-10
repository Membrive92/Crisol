import { Pressable, StyleSheet, Text, View } from 'react-native';

import {
  CATEGORY_COLOR_PALETTE,
  CATEGORY_EMOJI_PRESETS,
  colors,
  fontSize,
  fontWeight,
  radius,
  spacing,
} from '@finanzas/ui';

export interface AccountAppearanceFieldsProps {
  color: string | null;
  icon: string | null;
  onColorChange: (hex: string) => void;
  onIconChange: (emoji: string | null) => void;
}

/**
 * Pickers de color y emoji para cuentas (mobile). Reusa la misma paleta
 * y set de emojis que `CategoryAppearanceFields` (PHASE-19.1: cuentas y
 * categorías comparten estética).
 */
export function AccountAppearanceFields({
  color,
  icon,
  onColorChange,
  onIconChange,
}: AccountAppearanceFieldsProps) {
  return (
    <View style={styles.container}>
      <View>
        <Text style={styles.label}>Color</Text>
        <View style={styles.grid}>
          {CATEGORY_COLOR_PALETTE.map((preset) => {
            const selected =
              preset.hex.toLowerCase() === color?.toLowerCase();
            return (
              <Pressable
                key={preset.id}
                onPress={() => onColorChange(preset.hex)}
                accessibilityRole="radio"
                accessibilityState={{ selected }}
                accessibilityLabel={preset.label}
                style={[
                  styles.swatch,
                  { backgroundColor: preset.hex },
                  selected && styles.swatchSelected,
                ]}
              />
            );
          })}
        </View>
      </View>

      <View>
        <Text style={styles.label}>Icono</Text>
        <View style={styles.grid}>
          <Pressable
            onPress={() => onIconChange(null)}
            accessibilityRole="radio"
            accessibilityState={{ selected: !icon }}
            accessibilityLabel="Sin icono"
            style={[styles.emojiButton, !icon && styles.emojiButtonSelected]}
          >
            <Text style={styles.emojiPlaceholder}>—</Text>
          </Pressable>
          {CATEGORY_EMOJI_PRESETS.map((emoji) => {
            const selected = emoji === icon;
            return (
              <Pressable
                key={emoji}
                onPress={() => onIconChange(emoji)}
                accessibilityRole="radio"
                accessibilityState={{ selected }}
                accessibilityLabel={emoji}
                style={[
                  styles.emojiButton,
                  selected && styles.emojiButtonSelected,
                ]}
              >
                <Text style={styles.emojiText}>{emoji}</Text>
              </Pressable>
            );
          })}
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { gap: spacing.md },
  label: {
    fontSize: fontSize.sm,
    fontWeight: fontWeight.medium,
    color: colors.text,
    marginBottom: spacing.xs,
  },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.xs,
  },
  swatch: {
    width: 32,
    height: 32,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.border,
  },
  swatchSelected: {
    borderWidth: 3,
    borderColor: colors.text,
  },
  emojiButton: {
    width: 40,
    height: 40,
    borderRadius: radius.sm,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  emojiButtonSelected: {
    backgroundColor: colors.primarySoft,
    borderColor: colors.primary,
  },
  emojiText: { fontSize: fontSize.lg },
  emojiPlaceholder: {
    fontSize: fontSize.sm,
    color: colors.textMuted,
  },
});
