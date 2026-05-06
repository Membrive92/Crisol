import { useState } from 'react';
import { Alert, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Stack } from 'expo-router';

import {
  formatApiError,
  useCancelSubscription,
  useCategories,
  useConfirmSubscription,
  useDeleteSubscription,
  useDismissSubscription,
  usePauseSubscription,
  useResumeSubscription,
  useScanSubscriptions,
  useSubscriptions,
} from '@finanzas/services';
import { toast } from '@finanzas/store';
import { colors, fontSize, fontWeight, radius, spacing } from '@finanzas/ui';

import { SubscriptionCard } from '../../../components/subscriptions/subscription-card';

/**
 * Pantalla mobile de subscripciones (PHASE-13.3). Reusa hooks
 * shared de PHASE-13.2. Layout: header con descripción y botón
 * Re-escanear, sección Sugeridas (pendientes) con [Confirmar] /
 * [Descartar], sección Confirmadas con [Eliminar].
 */
export default function SubscriptionsScreen() {
  const { data: categories } = useCategories();
  const pendingQuery = useSubscriptions({ status: 'pending' });
  const confirmedQuery = useSubscriptions({ status: 'confirmed' });
  const dismissedQuery = useSubscriptions({ status: 'dismissed' });
  const pausedQuery = useSubscriptions({ status: 'paused' });
  const cancelledQuery = useSubscriptions({ status: 'cancelled' });
  const scanMutation = useScanSubscriptions();
  const confirmMutation = useConfirmSubscription();
  const dismissMutation = useDismissSubscription();
  const pauseMutation = usePauseSubscription();
  const resumeMutation = useResumeSubscription();
  const cancelMutation = useCancelSubscription();
  const deleteMutation = useDeleteSubscription();
  const [showDismissed, setShowDismissed] = useState(false);
  const [showCancelled, setShowCancelled] = useState(false);

  const pending = pendingQuery.data ?? [];
  const confirmed = confirmedQuery.data ?? [];
  const paused = pausedQuery.data ?? [];
  const cancelled = cancelledQuery.data ?? [];
  const dismissed = dismissedQuery.data ?? [];

  function handleScan() {
    scanMutation.mutate(undefined, {
      onSuccess: (res) =>
        toast.success(
          `Re-escaneado: ${res.created} nuevas, ${res.updated} actualizadas.`,
        ),
      onError: (err) => toast.error(formatApiError(err, 'Error al re-escanear.')),
    });
  }

  function handleConfirm(id: string) {
    confirmMutation.mutate(id, {
      onSuccess: () => toast.success('Subscripción confirmada.'),
      onError: (err) => toast.error(formatApiError(err, 'Error al confirmar.')),
    });
  }

  function handleReactivate(id: string) {
    // PHASE-13.1: confirm sobre una dismissed la reactiva.
    confirmMutation.mutate(id, {
      onSuccess: () => toast.success('Subscripción reactivada.'),
      onError: (err) => toast.error(formatApiError(err, 'Error al reactivar.')),
    });
  }

  function handleDismiss(id: string) {
    dismissMutation.mutate(id, {
      onSuccess: () => toast.info('Descartada — no se volverá a sugerir.'),
      onError: (err) => toast.error(formatApiError(err, 'Error al descartar.')),
    });
  }

  function handlePause(id: string) {
    pauseMutation.mutate(id, {
      onSuccess: () => toast.info('Subscripción pausada.'),
      onError: (err) => toast.error(formatApiError(err, 'Error al pausar.')),
    });
  }

  function handleResume(id: string) {
    resumeMutation.mutate(id, {
      onSuccess: () => toast.success('Subscripción reanudada.'),
      onError: (err) => toast.error(formatApiError(err, 'Error al reanudar.')),
    });
  }

  function handleCancel(id: string, label: string) {
    Alert.alert(
      'Cancelar subscripción',
      `Marca "${label}" como cancelada (ya no la tienes activa).`,
      [
        { text: 'Volver', style: 'cancel' },
        {
          text: 'Cancelar',
          style: 'destructive',
          onPress: () =>
            cancelMutation.mutate(id, {
              onSuccess: () => toast.info('Subscripción cancelada.'),
              onError: (err) =>
                toast.error(formatApiError(err, 'Error al cancelar.')),
            }),
        },
      ],
    );
  }

  function handleDelete(id: string, label: string) {
    Alert.alert(
      'Eliminar subscripción',
      `"${label}" desaparecerá. Si el patrón persiste, volverá a aparecer como pendiente en el próximo escaneo.`,
      [
        { text: 'Cancelar', style: 'cancel' },
        {
          text: 'Eliminar',
          style: 'destructive',
          onPress: () =>
            deleteMutation.mutate(id, {
              onSuccess: () => toast.success('Subscripción eliminada.'),
              onError: (err) =>
                toast.error(formatApiError(err, 'Error al eliminar.')),
            }),
        },
      ],
    );
  }

  const confirmingId = confirmMutation.isPending
    ? (confirmMutation.variables as string)
    : null;
  const dismissingId = dismissMutation.isPending
    ? (dismissMutation.variables as string)
    : null;
  const pausingId = pauseMutation.isPending
    ? (pauseMutation.variables as string)
    : null;
  const resumingId = resumeMutation.isPending
    ? (resumeMutation.variables as string)
    : null;
  const cancellingId = cancelMutation.isPending
    ? (cancelMutation.variables as string)
    : null;
  const deletingId = deleteMutation.isPending
    ? (deleteMutation.variables as string)
    : null;

  return (
    <View style={styles.container}>
      <Stack.Screen options={{ title: 'Subscripciones' }} />
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.intro}>
          Detectadas a partir de tus transacciones recurrentes (heurística
          local, sin enviar datos fuera). El detector se ejecuta cada noche;
          pulsa "Re-escanear" para forzarlo ahora.
        </Text>

        <Pressable
          onPress={handleScan}
          disabled={scanMutation.isPending}
          style={({ pressed }) => [
            styles.scanButton,
            pressed && { opacity: 0.7 },
            scanMutation.isPending && { opacity: 0.5 },
          ]}
        >
          <Text style={styles.scanButtonText}>
            {scanMutation.isPending ? 'Escaneando…' : 'Re-escanear'}
          </Text>
        </Pressable>

        <Text style={styles.sectionHeading}>Sugeridas</Text>
        {pendingQuery.isLoading ? (
          <Text style={styles.placeholder}>Cargando…</Text>
        ) : pending.length === 0 ? (
          <View style={styles.emptyCard}>
            <Text style={styles.emptyText}>
              Sin sugerencias pendientes. Cuando el detector encuentre un
              patrón nuevo aparecerá aquí.
            </Text>
          </View>
        ) : (
          pending.map((sub) => (
            <SubscriptionCard
              key={sub.id}
              subscription={sub}
              categories={categories ?? []}
              primaryAction={{
                label: 'Confirmar',
                onPress: () => handleConfirm(sub.id),
                busy: confirmingId === sub.id,
              }}
              secondaryAction={{
                label: 'Descartar',
                onPress: () => handleDismiss(sub.id),
                busy: dismissingId === sub.id,
              }}
            />
          ))
        )}

        {confirmed.length > 0 ? (
          <>
            <Text style={[styles.sectionHeading, { marginTop: spacing.lg }]}>
              Confirmadas
            </Text>
            {confirmed.map((sub) => (
              <SubscriptionCard
                key={sub.id}
                subscription={sub}
                categories={categories ?? []}
                primaryAction={{
                  label: 'Pausar',
                  onPress: () => handlePause(sub.id),
                  busy: pausingId === sub.id,
                }}
                secondaryAction={{
                  label: 'Cancelar',
                  onPress: () => handleCancel(sub.id, sub.raw_description),
                  busy: cancellingId === sub.id,
                  danger: true,
                }}
              />
            ))}
          </>
        ) : null}

        {paused.length > 0 ? (
          <>
            <Text style={[styles.sectionHeading, { marginTop: spacing.lg }]}>
              Pausadas
            </Text>
            {paused.map((sub) => (
              <SubscriptionCard
                key={sub.id}
                subscription={sub}
                categories={categories ?? []}
                primaryAction={{
                  label: 'Reanudar',
                  onPress: () => handleResume(sub.id),
                  busy: resumingId === sub.id,
                }}
                secondaryAction={{
                  label: 'Cancelar',
                  onPress: () => handleCancel(sub.id, sub.raw_description),
                  busy: cancellingId === sub.id,
                  danger: true,
                }}
              />
            ))}
          </>
        ) : null}

        {cancelled.length > 0 ? (
          <View style={{ marginTop: spacing.lg }}>
            <Pressable
              onPress={() => setShowCancelled((v) => !v)}
              style={({ pressed }) => [
                styles.toggleButton,
                pressed && { opacity: 0.7 },
              ]}
              accessibilityRole="button"
              accessibilityState={{ expanded: showCancelled }}
            >
              <Text style={styles.toggleText}>
                {showCancelled ? '▾' : '▸'} Canceladas ({cancelled.length})
              </Text>
            </Pressable>
            {showCancelled
              ? cancelled.map((sub) => (
                  <SubscriptionCard
                    key={sub.id}
                    subscription={sub}
                    categories={categories ?? []}
                    secondaryAction={{
                      label: 'Eliminar',
                      onPress: () => handleDelete(sub.id, sub.raw_description),
                      busy: deletingId === sub.id,
                      danger: true,
                    }}
                  />
                ))
              : null}
          </View>
        ) : null}

        {dismissed.length > 0 ? (
          <View style={{ marginTop: spacing.lg }}>
            <Pressable
              onPress={() => setShowDismissed((v) => !v)}
              style={({ pressed }) => [
                styles.toggleButton,
                pressed && { opacity: 0.7 },
              ]}
              accessibilityRole="button"
              accessibilityState={{ expanded: showDismissed }}
            >
              <Text style={styles.toggleText}>
                {showDismissed ? '▾' : '▸'} Descartadas ({dismissed.length})
              </Text>
            </Pressable>
            {showDismissed
              ? dismissed.map((sub) => (
                  <SubscriptionCard
                    key={sub.id}
                    subscription={sub}
                    categories={categories ?? []}
                    primaryAction={{
                      label: 'Reactivar',
                      onPress: () => handleReactivate(sub.id),
                      busy: confirmingId === sub.id,
                    }}
                    secondaryAction={{
                      label: 'Eliminar',
                      onPress: () => handleDelete(sub.id, sub.raw_description),
                      busy: deletingId === sub.id,
                      danger: true,
                    }}
                  />
                ))
              : null}
          </View>
        ) : null}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.md, paddingBottom: spacing.xxl },
  intro: { fontSize: fontSize.sm, color: colors.textMuted, marginBottom: spacing.md },
  scanButton: {
    alignSelf: 'flex-start',
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.md,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.primary,
    backgroundColor: 'transparent',
    marginBottom: spacing.lg,
  },
  scanButtonText: {
    color: colors.primary,
    fontSize: fontSize.sm,
    fontWeight: fontWeight.semibold,
  },
  sectionHeading: {
    fontSize: fontSize.md,
    fontWeight: fontWeight.semibold,
    color: colors.text,
    marginBottom: spacing.sm,
  },
  placeholder: { padding: spacing.md, color: colors.textMuted },
  emptyCard: {
    backgroundColor: colors.surfaceMuted,
    borderColor: colors.border,
    borderStyle: 'dashed',
    borderWidth: 1,
    borderRadius: radius.md,
    padding: spacing.lg,
    alignItems: 'center',
  },
  emptyText: {
    fontSize: fontSize.sm,
    color: colors.textMuted,
    textAlign: 'center',
  },
  toggleButton: {
    paddingVertical: spacing.xs,
    marginBottom: spacing.sm,
    alignSelf: 'flex-start',
  },
  toggleText: {
    fontSize: fontSize.sm,
    color: colors.textMuted,
    fontWeight: fontWeight.medium,
  },
});
