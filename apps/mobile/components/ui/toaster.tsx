import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { useToastStore } from '@finanzas/store';
import type { Toast, ToastKind } from '@finanzas/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@finanzas/ui';

import { Spinner } from './spinner';

/**
 * Stack inferior de toasts globales (PHASE-11.3). Equivalente al
 * `<Toaster />` web — escucha la queue de `useToastStore` y la
 * renderiza con auto-dismiss.
 *
 * Posición fija bottom para que no compita con el header (Stack
 * de Expo Router) y sobreviva scroll.
 */
export function Toaster() {
  const toasts = useToastStore((s) => s.toasts);

  if (toasts.length === 0) return null;

  return (
    <View style={styles.stack} pointerEvents="box-none">
      {toasts.map((t) => (
        <ToastCard key={t.id} toast={t} />
      ))}
    </View>
  );
}

function ToastCard({ toast }: { toast: Toast }) {
  const dismiss = useToastStore((s) => s.dismiss);

  useEffect(() => {
    if (toast.dismissAfterMs <= 0) return;
    const timer = setTimeout(() => dismiss(toast.id), toast.dismissAfterMs);
    return () => clearTimeout(timer);
  }, [toast.id, toast.dismissAfterMs, dismiss]);

  const palette = paletteFor(toast.kind);
  const isLoading = toast.kind === 'loading';

  return (
    <View
      style={[styles.toast, { borderLeftColor: palette.accent }]}
      accessibilityLiveRegion={toast.kind === 'error' ? 'assertive' : 'polite'}
    >
      {isLoading ? <Spinner size="small" color={colors.surface} /> : null}
      <View style={{ flex: 1, flexDirection: 'row', alignItems: 'center' }}>
        <Text style={styles.message} numberOfLines={3}>
          {toast.message}
        </Text>
        {isLoading ? <ElapsedTime /> : null}
      </View>
      {toast.action ? (
        <Pressable
          onPress={() => {
            toast.action?.onPress();
            dismiss(toast.id);
          }}
          style={({ pressed }) => [styles.action, pressed && styles.actionPressed]}
        >
          <Text style={[styles.actionText, { color: palette.accent }]}>
            {toast.action.label}
          </Text>
        </Pressable>
      ) : null}
      {/* Loading toasts solo se cierran programáticamente. */}
      {!isLoading ? (
        <Pressable
          accessibilityLabel="Cerrar"
          onPress={() => dismiss(toast.id)}
          style={({ pressed }) => [styles.close, pressed && styles.closePressed]}
        >
          <Text style={styles.closeText}>×</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

function ElapsedTime() {
  const [start] = useState(() => Date.now());
  const [now, setNow] = useState(start);
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);
  const seconds = Math.floor((now - start) / 1000);
  const mm = Math.floor(seconds / 60).toString().padStart(2, '0');
  const ss = (seconds % 60).toString().padStart(2, '0');
  return (
    <Text style={styles.elapsed}>
      {' '}
      ({mm}:{ss})
    </Text>
  );
}

function paletteFor(kind: ToastKind): { accent: string } {
  switch (kind) {
    case 'success':
      return { accent: colors.success };
    case 'warning':
      return { accent: colors.warning };
    case 'error':
      return { accent: colors.danger };
    case 'loading':
    case 'info':
    default:
      return { accent: colors.primary };
  }
}

const styles = StyleSheet.create({
  stack: {
    position: 'absolute',
    left: spacing.md,
    right: spacing.md,
    bottom: spacing.md,
    gap: spacing.sm,
  },
  toast: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    backgroundColor: colors.text,
    borderLeftWidth: 3,
    borderRadius: radius.md,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
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
  },
  elapsed: {
    color: colors.surface,
    opacity: 0.7,
    fontSize: fontSize.xs,
  },
  action: {
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.sm,
    borderRadius: radius.sm,
  },
  actionPressed: { backgroundColor: 'rgba(255,255,255,0.1)' },
  actionText: { fontSize: fontSize.sm, fontWeight: fontWeight.semibold },
  close: { padding: 4 },
  closePressed: { opacity: 0.6 },
  closeText: {
    color: colors.surface,
    fontSize: 18,
    fontWeight: fontWeight.bold,
    lineHeight: 18,
  },
});
