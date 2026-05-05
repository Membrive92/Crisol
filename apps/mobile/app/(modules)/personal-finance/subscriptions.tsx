import { Alert, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Stack } from 'expo-router';

import {
  formatApiError,
  useCategories,
  useConfirmSubscription,
  useDeleteSubscription,
  useDismissSubscription,
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
  const scanMutation = useScanSubscriptions();
  const confirmMutation = useConfirmSubscription();
  const dismissMutation = useDismissSubscription();
  const deleteMutation = useDeleteSubscription();

  const pending = pendingQuery.data ?? [];
  const confirmed = confirmedQuery.data ?? [];

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

  function handleDismiss(id: string) {
    dismissMutation.mutate(id, {
      onSuccess: () => toast.info('Descartada — no se volverá a sugerir.'),
      onError: (err) => toast.error(formatApiError(err, 'Error al descartar.')),
    });
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
                secondaryAction={{
                  label: 'Eliminar',
                  onPress: () => handleDelete(sub.id, sub.raw_description),
                  busy: deletingId === sub.id,
                  danger: true,
                }}
              />
            ))}
          </>
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
});
