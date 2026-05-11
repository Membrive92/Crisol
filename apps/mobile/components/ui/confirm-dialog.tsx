import type { ReactNode } from 'react';
import {
  Modal,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';

export type ConfirmDialogTone = 'danger' | 'primary';

export interface ConfirmDialogProps {
  open: boolean;
  title: string;
  description?: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  tone?: ConfirmDialogTone;
  loading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = 'Eliminar',
  cancelLabel = 'Cancelar',
  tone = 'danger',
  loading = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  return (
    <Modal
      transparent
      visible={open}
      animationType="fade"
      onRequestClose={() => {
        if (!loading) onCancel();
      }}
    >
      <Pressable
        style={styles.backdrop}
        onPress={() => {
          if (!loading) onCancel();
        }}
      >
        <Pressable
          style={styles.card}
          onPress={(e) => e.stopPropagation()}
          accessibilityRole="alert"
          accessibilityLabel={title}
        >
          <Text style={styles.title}>{title}</Text>
          {description ? (
            typeof description === 'string' ? (
              <Text style={styles.description}>{description}</Text>
            ) : (
              <View style={{ marginTop: spacing.sm }}>{description}</View>
            )
          ) : null}
          <View style={styles.actions}>
            <Pressable
              onPress={onCancel}
              disabled={loading}
              style={({ pressed }) => [
                styles.secondaryButton,
                pressed && styles.pressed,
                loading && styles.disabled,
              ]}
            >
              <Text style={styles.secondaryButtonText}>{cancelLabel}</Text>
            </Pressable>
            <Pressable
              onPress={onConfirm}
              disabled={loading}
              style={({ pressed }) => [
                tone === 'danger' ? styles.dangerButton : styles.primaryButton,
                pressed && styles.pressed,
                loading && styles.disabled,
              ]}
            >
              <Text style={styles.primaryButtonText}>
                {loading ? 'Procesando…' : confirmLabel}
              </Text>
            </Pressable>
          </View>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.lg,
  },
  card: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.md,
    padding: spacing.lg,
    width: '100%',
    maxWidth: 420,
  },
  title: {
    fontSize: fontSize.lg,
    fontWeight: fontWeight.semibold,
    color: colors.text,
  },
  description: {
    marginTop: spacing.sm,
    fontSize: fontSize.sm,
    color: colors.textMuted,
    lineHeight: 20,
  },
  actions: {
    flexDirection: 'row',
    gap: spacing.sm,
    justifyContent: 'flex-end',
    marginTop: spacing.md,
  },
  secondaryButton: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: 'transparent',
  },
  secondaryButtonText: {
    color: colors.text,
    fontSize: fontSize.sm,
    fontWeight: fontWeight.medium,
  },
  primaryButton: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.sm,
    backgroundColor: colors.primary,
  },
  dangerButton: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.sm,
    backgroundColor: colors.danger,
  },
  primaryButtonText: {
    color: colors.onPrimary,
    fontSize: fontSize.sm,
    fontWeight: fontWeight.semibold,
  },
  pressed: {
    opacity: 0.7,
  },
  disabled: {
    opacity: 0.5,
  },
});
