import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Stack, useRouter } from 'expo-router';

import {
  useAccountBalances,
  useAccounts,
  useDebtHistory,
} from '@crisol/services';
import type { Account } from '@crisol/types';
import {
  colors,
  fontSize,
  fontWeight,
  spacing,
} from '@crisol/ui';

import { DebtPaymentWizard } from '../../../components/accounts/debt-payment-wizard';
import { DebtHealthCard } from '../../../components/dashboard/debt-health-card';
import { DebtList } from '../../../components/debt/debt-list';
import { DebtTrendChart } from '../../../components/debt/debt-trend-chart';

/**
 * Módulo Deuda (PHASE-22+, promocionado a top-level) — pantalla
 * principal. Agrega los tres bloques en orden: KPIs de salud
 * (`DebtHealthCard`), evolución temporal histórico+proyección
 * (`DebtTrendChart`) y lista de pasivos con acciones (`DebtList`).
 * Botón superior "Añadir deuda" lleva al gestor de cuentas dentro de
 * Finanzas Domésticas.
 */
export default function DebtScreen() {
  const router = useRouter();
  const balancesQuery = useAccountBalances();
  const accountsQuery = useAccounts({ includeArchived: false });
  const historyQuery = useDebtHistory({ monthsBack: 12, monthsAhead: 12 });
  const [payingDebt, setPayingDebt] = useState<Account | null>(null);

  const balances = balancesQuery.data?.items ?? [];
  const accounts = accountsQuery.data ?? [];
  const history = historyQuery.data?.items ?? [];
  const currency = historyQuery.data?.reference_currency ?? 'EUR';

  return (
    <>
      <Stack.Screen options={{ title: 'Deuda' }} />
      <ScrollView
        style={styles.container}
        contentContainerStyle={styles.content}
      >
        <View style={styles.header}>
          <View style={{ flex: 1 }}>
            <Text style={styles.eyebrow}>MONITORIZACIÓN · LOCAL</Text>
            <Text style={styles.title}>Deuda</Text>
            <Text style={styles.subtitle}>
              Salud financiera, evolución mes a mes y acciones por pasivo.
            </Text>
          </View>
          <Pressable
            style={({ pressed }) => [
              styles.addButton,
              pressed && { opacity: 0.85 },
            ]}
            onPress={() => router.push('/personal-finance/accounts')}
          >
            <Text style={styles.addButtonText}>Añadir deuda</Text>
          </Pressable>
        </View>

        <View style={styles.section}>
          <DebtHealthCard />
        </View>

        <View style={styles.section}>
          <DebtTrendChart
            data={history}
            currency={currency}
            isLoading={historyQuery.isLoading}
          />
        </View>

        <View style={styles.section}>
          <DebtList
            balances={balances}
            accounts={accounts}
            isLoading={balancesQuery.isLoading || accountsQuery.isLoading}
            onPayDebt={setPayingDebt}
          />
        </View>
      </ScrollView>

      {payingDebt ? (
        <DebtPaymentWizard
          liabilityAccount={payingDebt}
          visible={payingDebt !== null}
          onClose={() => setPayingDebt(null)}
        />
      ) : null}
    </>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    padding: spacing.lg,
    gap: spacing.md,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    justifyContent: 'space-between',
    gap: spacing.sm,
    marginBottom: spacing.sm,
  },
  eyebrow: {
    fontSize: 11,
    fontWeight: fontWeight.semibold,
    color: colors.primary,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
  },
  title: {
    fontSize: fontSize.xl,
    fontWeight: fontWeight.bold,
    color: colors.text,
    marginTop: spacing.xs,
  },
  subtitle: {
    fontSize: fontSize.sm,
    color: colors.textMuted,
    marginTop: spacing.xs,
    lineHeight: 20,
  },
  addButton: {
    backgroundColor: colors.primary,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: 8,
  },
  addButtonText: {
    color: colors.onPrimary,
    fontWeight: fontWeight.semibold,
    fontSize: fontSize.sm,
  },
  section: {
    marginBottom: spacing.sm,
  },
});
