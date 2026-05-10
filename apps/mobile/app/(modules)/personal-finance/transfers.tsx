import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Stack } from 'expo-router';

import {
  formatApiError,
  useAccounts,
  useLinkTransfer,
  useMatchTransfers,
  useTransferCandidates,
  useTransfers,
  useUnlinkTransfer,
} from '@finanzas/services';
import { toast } from '@finanzas/store';
import {
  colors,
  fontSize,
  fontWeight,
  radius,
  spacing,
} from '@finanzas/ui';

import { TransferPairCard } from '../../../components/transfers/transfer-pair-card';
import { ConfirmDialog } from '../../../components/ui/confirm-dialog';

/**
 * Pantalla mobile de gestión de transferencias internas (PHASE-19.3).
 * Espejo de `apps/web/app/(app)/personal-finance/transfers/page.tsx`.
 *
 * Layout:
 *  - Intro + botón "Detectar automáticas".
 *  - "Pares activos" (`useTransfers`) con [Deshacer] confirm-dialogeado.
 *  - "Sugerencias pendientes" (`useTransferCandidates(3)`) con [Enlazar],
 *    sólo si hay candidatos.
 */
export default function TransfersScreen() {
  const transfersQuery = useTransfers();
  const candidatesQuery = useTransferCandidates(3);
  // includeArchived: cuentas archivadas pueden formar parte de pares
  // históricos — necesitamos su nombre/color/icon para resolver el
  // display, aunque ya no aparezcan en selectors.
  const accountsQuery = useAccounts({ includeArchived: true });

  const matchMutation = useMatchTransfers();
  const linkMutation = useLinkTransfer();
  const unlinkMutation = useUnlinkTransfer();

  const [pendingUnlink, setPendingUnlink] = useState<
    { outId: string; amount: string; currency: string } | null
  >(null);

  const pairs = transfersQuery.data ?? [];
  const candidates = candidatesQuery.data ?? [];
  const accounts = accountsQuery.data ?? [];

  function handleAutoMatch() {
    matchMutation.mutate(undefined, {
      onSuccess: (response) => {
        const linked = response.linked_count;
        const pending = response.pending_candidates.length;
        if (linked === 0 && pending === 0) {
          toast.info('No se han encontrado nuevas transferencias.');
          return;
        }
        const parts: string[] = [];
        if (linked > 0) {
          parts.push(`${linked} ${linked === 1 ? 'par enlazado' : 'pares enlazados'}`);
        }
        if (pending > 0) {
          parts.push(
            `${pending} ${
              pending === 1 ? 'candidato ambiguo' : 'candidatos ambiguos'
            } esperando confirmación`,
          );
        }
        toast.success(parts.join(' · '));
      },
      onError: (err) =>
        toast.error(formatApiError(err, 'Error al detectar transferencias.')),
    });
  }

  function handleLink(outId: string, inId: string) {
    linkMutation.mutate(
      { out_transaction_id: outId, in_transaction_id: inId },
      {
        onSuccess: () => toast.success('Par enlazado.'),
        onError: (err) => toast.error(formatApiError(err, 'Error al enlazar.')),
      },
    );
  }

  function confirmUnlink() {
    if (!pendingUnlink) return;
    const { outId } = pendingUnlink;
    setPendingUnlink(null);
    unlinkMutation.mutate(outId, {
      onSuccess: () => toast.info('Par deshecho.'),
      onError: (err) => toast.error(formatApiError(err, 'Error al deshacer.')),
    });
  }

  // Sólo mostramos la sección "Sugerencias" si hay candidatos pendientes
  // — si la lista está vacía y no hay pares, esconder la sección entera
  // evita ruido en la primera carga.
  const showSuggestions = candidates.length > 0;

  return (
    <View style={styles.container}>
      <Stack.Screen options={{ title: 'Transferencias internas' }} />
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.intro}>
          Cuando muevas dinero entre tus propias cuentas, enlaza la salida y la
          entrada para que no cuenten como gasto/ingreso real. Sí afectan al
          saldo de cada cuenta, pero quedan fuera del cashflow, la tasa de
          ahorro y los presupuestos.
        </Text>

        <Pressable
          onPress={handleAutoMatch}
          disabled={matchMutation.isPending}
          style={({ pressed }) => [
            styles.scanButton,
            pressed && { opacity: 0.7 },
            matchMutation.isPending && { opacity: 0.5 },
          ]}
        >
          <Text style={styles.scanButtonText}>
            {matchMutation.isPending ? 'Detectando…' : 'Detectar automáticas'}
          </Text>
        </Pressable>

        <Text style={styles.sectionHeading}>Pares activos</Text>
        {transfersQuery.isLoading ? (
          <Text style={styles.placeholder}>Cargando…</Text>
        ) : pairs.length === 0 ? (
          <View style={styles.emptyCard}>
            <Text style={styles.emptyText}>
              Aún no hay pares enlazados. Pulsa "Detectar automáticas" para que
              el detector busque candidatos en tus transacciones.
            </Text>
          </View>
        ) : (
          pairs.map((pair) => {
            const busy =
              unlinkMutation.isPending &&
              unlinkMutation.variables === pair.out_transaction_id;
            return (
              <TransferPairCard
                key={`${pair.out_transaction_id}-${pair.in_transaction_id}`}
                pair={pair}
                accounts={accounts}
                primaryAction={{
                  label: 'Deshacer',
                  onPress: () =>
                    setPendingUnlink({
                      outId: pair.out_transaction_id,
                      amount: pair.amount,
                      currency: pair.currency,
                    }),
                  variant: 'ghost',
                  busy,
                }}
              />
            );
          })
        )}

        {showSuggestions ? (
          <>
            <Text style={[styles.sectionHeading, { marginTop: spacing.lg }]}>
              Sugerencias pendientes
            </Text>
            <Text style={styles.suggestionsHint}>
              Estas parejas tienen el mismo importe y fechas próximas pero el
              matcher no las enlazó automáticamente (suelen ser ambiguas porque
              hay varios candidatos coincidentes). Confírmalas una a una.
            </Text>
            {candidates.map((candidate) => {
              const variables = linkMutation.variables;
              const busy =
                linkMutation.isPending &&
                variables?.out_transaction_id === candidate.out_transaction_id &&
                variables?.in_transaction_id === candidate.in_transaction_id;
              return (
                <TransferPairCard
                  key={`${candidate.out_transaction_id}-${candidate.in_transaction_id}`}
                  pair={candidate}
                  accounts={accounts}
                  primaryAction={{
                    label: 'Enlazar',
                    onPress: () =>
                      handleLink(
                        candidate.out_transaction_id,
                        candidate.in_transaction_id,
                      ),
                    variant: 'primary',
                    busy,
                  }}
                />
              );
            })}
          </>
        ) : null}
      </ScrollView>

      <ConfirmDialog
        open={pendingUnlink !== null}
        title="¿Deshacer transferencia?"
        description={
          pendingUnlink
            ? `Las dos transacciones de ${pendingUnlink.amount} ${pendingUnlink.currency} volverán a contar como gasto/ingreso normal.`
            : undefined
        }
        confirmLabel="Deshacer"
        cancelLabel="Atrás"
        tone="primary"
        loading={unlinkMutation.isPending}
        onConfirm={confirmUnlink}
        onCancel={() => setPendingUnlink(null)}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.md, paddingBottom: spacing.xxl },
  intro: {
    fontSize: fontSize.sm,
    color: colors.textMuted,
    marginBottom: spacing.md,
    lineHeight: 18,
  },
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
  suggestionsHint: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
    marginBottom: spacing.sm,
    lineHeight: 16,
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
