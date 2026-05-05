import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { colors, fontSize, fontWeight, radius, spacing } from '@finanzas/ui';

export interface TrashedSnackbarProps {
  /**
   * ID de la última transacción borrada. Cambiar a un ID nuevo
   * activa el snackbar; pasar `null` lo oculta. Auto-dismiss tras
   * `dismissAfterMs`.
   */
  lastDeletedId: string | null;
  onUndo: () => void;
  onViewTrash: () => void;
  isRestoring: boolean;
  /** Por defecto 6s — alineado con el banner web. */
  dismissAfterMs?: number;
}

/**
 * Notificación inferior tras un soft-delete: "Movido a papelera" +
 * acciones [Deshacer] y [Ver papelera]. Equivalente a `TrashedBanner`
 * en web — vista nativa con `Pressable`. Vive en el bottom de la
 * pantalla con `position: 'absolute'` para que sea visible aunque la
 * lista esté scrolleada.
 */
export function TrashedSnackbar({
  lastDeletedId,
  onUndo,
  onViewTrash,
  isRestoring,
  dismissAfterMs = 6000,
}: TrashedSnackbarProps) {
  const [visibleId, setVisibleId] = useState<string | null>(null);

  useEffect(() => {
    setVisibleId(lastDeletedId);
  }, [lastDeletedId]);

  useEffect(() => {
    if (!visibleId) return;
    const timer = setTimeout(() => setVisibleId(null), dismissAfterMs);
    return () => clearTimeout(timer);
  }, [visibleId, dismissAfterMs]);

  if (!visibleId) return null;

  return (
    <View style={styles.snackbar} accessibilityLiveRegion="polite">
      <Text style={styles.message}>Movida a papelera.</Text>
      <View style={styles.actions}>
        <Pressable
          onPress={() => {
            onUndo();
            setVisibleId(null);
          }}
          disabled={isRestoring}
          style={({ pressed }) => [styles.action, pressed && styles.actionPressed]}
        >
          <Text style={styles.actionText}>
            {isRestoring ? 'Restaurando…' : 'Deshacer'}
          </Text>
        </Pressable>
        <Pressable
          onPress={() => {
            onViewTrash();
            setVisibleId(null);
          }}
          style={({ pressed }) => [styles.action, pressed && styles.actionPressed]}
        >
          <Text style={styles.actionText}>Ver</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  snackbar: {
    position: 'absolute',
    left: spacing.md,
    right: spacing.md,
    bottom: spacing.md,
    backgroundColor: colors.text,
    borderRadius: radius.md,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.2,
    shadowRadius: 6,
    elevation: 4,
  },
  message: {
    color: colors.surface,
    fontSize: fontSize.sm,
    fontWeight: fontWeight.medium,
    flex: 1,
  },
  actions: {
    flexDirection: 'row',
    gap: spacing.sm,
  },
  action: {
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.sm,
    borderRadius: radius.sm,
  },
  actionPressed: {
    backgroundColor: 'rgba(255,255,255,0.1)',
  },
  actionText: {
    color: colors.primarySoft,
    fontSize: fontSize.sm,
    fontWeight: fontWeight.semibold,
  },
});
