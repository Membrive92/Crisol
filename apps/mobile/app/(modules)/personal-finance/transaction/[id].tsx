import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';

import {
  formatApiError,
  useTransaction,
  useUpdateTransaction,
} from '@crisol/services';
import { toast } from '@crisol/store';
import type { TransactionUpdateRequest } from '@crisol/types';
import { colors, fontSize, spacing } from '@crisol/ui';

import { TransactionForm } from '../../../../components/transaction-form';
import {
  ConvertToDebtBlock,
  looksLikeFinancedOperation,
} from '../../../../components/transfers/convert-to-debt-block';
import { ConvertToTransferBlock } from '../../../../components/transfers/convert-to-transfer-block';

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
    <ScrollView contentContainerStyle={styles.scroll}>
      <TransactionForm
        initial={data}
        submitLabel="Guardar"
        submitting={mutation.isPending}
        onSubmit={(payload) => handleSubmit(payload as TransactionUpdateRequest)}
        onCancel={() => router.back()}
      />
      {data.transfer_pair_id === null ? (
        <>
          <ConvertToTransferBlock
            transaction={data}
            onConverted={(pair) => {
              toast.success(
                `Transferencia creada (${pair.amount} ${pair.currency}).`,
              );
              router.replace('/(modules)/personal-finance/transfers');
            }}
            onError={(err) =>
              toast.error(formatApiError(err, 'No se pudo convertir.'))
            }
          />
          <ConvertToDebtBlock
            transaction={data}
            suggested={looksLikeFinancedOperation(data.description)}
            onConverted={(pair) => {
              toast.success(
                `Deuda registrada (${pair.amount} ${pair.currency}).`,
              );
              router.replace('/(modules)/personal-finance/accounts');
            }}
            onError={(err) =>
              toast.error(formatApiError(err, 'No se pudo registrar la deuda.'))
            }
          />
        </>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  scroll: {
    padding: spacing.md,
    paddingBottom: spacing.xxl,
    backgroundColor: colors.background,
  },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.lg,
    backgroundColor: colors.background,
  },
  placeholder: { fontSize: fontSize.md, color: colors.textMuted },
});
