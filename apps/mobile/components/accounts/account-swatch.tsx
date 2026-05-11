import { StyleSheet, Text, View } from 'react-native';

import { DEFAULT_CATEGORY_COLOR, colors, fontSize } from '@crisol/ui';

export interface AccountSwatchProps {
  color: string | null;
  icon: string | null;
  size?: number;
}

/**
 * Avatar circular para una cuenta — color de fondo + emoji opcional.
 * Espejo del `AccountSwatch` web; coincide visualmente con
 * `CategorySwatch` (categories.tsx) por coherencia: ambos representan
 * entidades coloreables del usuario.
 */
export function AccountSwatch({ color, icon, size = 32 }: AccountSwatchProps) {
  const bg = color ?? DEFAULT_CATEGORY_COLOR;
  return (
    <View
      style={[
        styles.swatch,
        {
          width: size,
          height: size,
          borderRadius: size / 2,
          backgroundColor: bg,
        },
      ]}
      accessibilityElementsHidden
      importantForAccessibility="no"
    >
      {icon ? <Text style={styles.icon}>{icon}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  swatch: {
    alignItems: 'center',
    justifyContent: 'center',
    borderColor: colors.border,
  },
  icon: { fontSize: fontSize.md, lineHeight: fontSize.md + 2 },
});
