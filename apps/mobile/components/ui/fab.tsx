import { useRouter } from 'expo-router';
import { Pressable, StyleSheet, Text } from 'react-native';

import { colors, fontWeight } from '@finanzas/ui';

export interface FabLinkProps {
  href: string;
  ariaLabel: string;
  label?: string;
}

/**
 * Botón flotante circular contextual. Usa expo-router para navegación.
 * Sólido con color primario; respeta `colors.onPrimary` como texto.
 */
export function FabLink({ href, ariaLabel, label = '+' }: FabLinkProps) {
  const router = useRouter();
  return (
    <Pressable
      accessibilityLabel={ariaLabel}
      accessibilityRole="button"
      onPress={() => router.push(href as never)}
      style={({ pressed }) => [styles.fab, pressed && styles.fabPressed]}
    >
      <Text style={styles.label}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  fab: {
    position: 'absolute',
    right: 24,
    bottom: 24,
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.32,
    shadowRadius: 16,
    elevation: 8,
  },
  fabPressed: { opacity: 0.85, transform: [{ scale: 0.97 }] },
  label: {
    color: colors.onPrimary,
    fontSize: 28,
    fontWeight: fontWeight.bold,
    lineHeight: 30,
  },
});
