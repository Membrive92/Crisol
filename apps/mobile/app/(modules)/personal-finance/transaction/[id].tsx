import { StyleSheet, Text, View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';

import { useTransaction, useUpdateTransaction } from '@crisol/services';
import type { TransactionUpdateRequest } from '@crisol/types';
import { colors, fontSize, spacing } from '@crisol/ui';

import { TransactionForm } from '../../../../components/transaction-form';

export default function EditTransactionScreen() {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const { data, isLoading, isError } = useTransaction(id);
  const mutation = useUpdateTransaction(id ?? '');

  function handleSubmit(payload: TransactionUpdateRequest) {
    mutation.mutate(payload, {
      onSuccess: () => router.back(),
    });
  }

  if (isLoading) {
    return (
      <View style={styles.center}>
        <Text style={styles.placeholder}>Cargando…</Text>
      </View>
    );
  }

  if (isError || !data) {
    return (
      <View style={styles.center}>
        <Text style={[styles.placeholder, { color: colors.danger }]}>
          No se pudo cargar la transacción.
        </Text>
      </View>
    );
  }

  return (
    <TransactionForm
      initial={data}
      submitLabel="Guardar"
      submitting={mutation.isPending}
      onSubmit={(payload) => handleSubmit(payload as TransactionUpdateRequest)}
      onCancel={() => router.back()}
    />
  );
}

const styles = StyleSheet.create({
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.lg,
    backgroundColor: colors.background,
  },
  placeholder: { fontSize: fontSize.md, color: colors.textMuted },
});
