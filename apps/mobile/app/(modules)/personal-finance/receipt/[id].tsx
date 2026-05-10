import { useState } from 'react';
import {
  Image,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';

import {
  useConfirmReceipt,
  useReceipt,
  useReceiptImage,
  useRejectReceipt,
} from '@finanzas/services';
import type { ReceiptConfirmRequest } from '@finanzas/types';
import { colors, fontSize, fontWeight, formatDate, radius, spacing } from '@finanzas/ui';

import { ReceiptCaptureForm } from '@/components/receipt-capture-form';
import { ConfirmDialog } from '@/components/ui/confirm-dialog';

const STATUS_LABEL = {
  pending: 'Pendiente',
  confirmed: 'Confirmado',
  rejected: 'Rechazado',
} as const;

const STATUS_COLOR = {
  pending: colors.primary,
  confirmed: colors.success,
  rejected: colors.danger,
} as const;

export default function ReceiptDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();

  const { data: receipt, isLoading, isError } = useReceipt(id);
  const { url: imageUrl, isLoading: imageLoading } = useReceiptImage(id);
  const confirmMutation = useConfirmReceipt(id ?? '');
  const rejectMutation = useRejectReceipt(id ?? '');
  const [confirmingReject, setConfirmingReject] = useState(false);

  function handleConfirm(payload: ReceiptConfirmRequest) {
    if (!receipt) return;
    confirmMutation.mutate(payload, {
      onSuccess: () => router.replace('/(modules)/personal-finance/(tabs)/receipts'),
    });
  }

  function handleReject() {
    if (!receipt) return;
    setConfirmingReject(true);
  }

  function confirmReject() {
    if (!receipt) return;
    setConfirmingReject(false);
    rejectMutation.mutate();
  }

  if (isLoading) {
    return (
      <View style={styles.center}>
        <Text style={styles.muted}>Cargando…</Text>
      </View>
    );
  }
  if (isError || !receipt) {
    return (
      <View style={styles.center}>
        <Text style={styles.muted}>Ticket no encontrado.</Text>
      </View>
    );
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.headerRow}>
        <View style={[styles.badge, { backgroundColor: STATUS_COLOR[receipt.status] }]}>
          <Text style={styles.badgeText}>{STATUS_LABEL[receipt.status]}</Text>
        </View>
        <Text style={styles.muted}>{formatDate(receipt.created_at)}</Text>
      </View>

      <View style={styles.imageWrapper}>
        {imageLoading ? (
          <Text style={styles.muted}>Cargando imagen…</Text>
        ) : imageUrl ? (
          <Image source={{ uri: imageUrl }} style={styles.image} />
        ) : (
          <Text style={styles.muted}>No se pudo cargar la imagen.</Text>
        )}
      </View>

      <View style={styles.card}>
        {receipt.status === 'pending' ? (
          <ReceiptCaptureForm
            extraction={receipt.extraction}
            submitting={confirmMutation.isPending || rejectMutation.isPending}
            errorMessage={
              confirmMutation.isError
                ? confirmMutation.error instanceof Error
                  ? confirmMutation.error.message
                  : 'Error al confirmar'
                : null
            }
            onSubmit={handleConfirm}
            onReject={handleReject}
          />
        ) : (
          <Text style={styles.muted}>
            Este ticket ya fue {receipt.status === 'confirmed' ? 'confirmado' : 'rechazado'}.
          </Text>
        )}
      </View>

      <TouchableOpacity onPress={() => router.back()}>
        <Text style={styles.link}>← Volver</Text>
      </TouchableOpacity>

      <ConfirmDialog
        open={confirmingReject}
        title="¿Rechazar este ticket?"
        description="La transacción no se creará y el ticket quedará marcado como rechazado."
        confirmLabel="Rechazar"
        cancelLabel="Atrás"
        tone="danger"
        loading={rejectMutation.isPending}
        onConfirm={confirmReject}
        onCancel={() => setConfirmingReject(false)}
      />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.lg },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: spacing.lg },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginBottom: spacing.md,
  },
  badge: {
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: radius.sm,
  },
  badgeText: {
    color: colors.surface,
    fontSize: fontSize.xs,
    fontWeight: fontWeight.semibold as '600',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  imageWrapper: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: radius.md,
    minHeight: 200,
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  image: {
    width: '100%',
    height: 320,
    resizeMode: 'contain',
    borderRadius: radius.sm,
  },
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: spacing.lg,
  },
  muted: { color: colors.textMuted, fontSize: fontSize.sm, textAlign: 'center' },
  link: {
    color: colors.primary,
    fontSize: fontSize.sm,
    fontWeight: fontWeight.medium as '500',
    textAlign: 'center',
    paddingVertical: spacing.md,
  },
});
