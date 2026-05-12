import { useMemo } from 'react';
import { FlatList, StyleSheet, Text, View } from 'react-native';
import { Stack, useLocalSearchParams } from 'expo-router';

import {
  formatApiError,
  useAccount,
  useAccountBalances,
  useAmortizationSchedule,
} from '@crisol/services';
import type { AmortizationRow } from '@crisol/types';
import {
  colors,
  fontSize,
  fontWeight,
  formatAmount,
  formatDate,
  radius,
  spacing,
} from '@crisol/ui';

import { AccountSwatch } from '../../../../../components/accounts/account-swatch';

/**
 * Formatea un total de meses como "X años Y meses" o "Y meses" si <12.
 */
function formatMonthsAsDuration(months: number): string {
  if (months <= 0) return '—';
  const years = Math.floor(months / 12);
  const remainder = months - years * 12;
  if (years === 0) return `${remainder} ${remainder === 1 ? 'mes' : 'meses'}`;
  if (remainder === 0) return `${years} ${years === 1 ? 'año' : 'años'}`;
  return `${years} ${years === 1 ? 'año' : 'años'} ${remainder} ${remainder === 1 ? 'mes' : 'meses'}`;
}

/**
 * Cuenta cuántos meses han pasado entre `start_date` y la fecha actual.
 * Devuelve un valor en `[0, term_months]` — sin meses negativos ni
 * mayores que el plazo total.
 */
function monthsElapsedSince(startDate: string, totalMonths: number): number {
  const start = new Date(`${startDate}T00:00:00Z`);
  if (Number.isNaN(start.getTime())) return 0;
  const now = new Date();
  const elapsed =
    (now.getFullYear() - start.getFullYear()) * 12 +
    (now.getMonth() - start.getMonth());
  if (elapsed < 0) return 0;
  if (elapsed > totalMonths) return totalMonths;
  return elapsed;
}

/**
 * Pantalla de cuadro de amortización (PHASE-22) mobile. Espejo de
 * `apps/web/app/(app)/personal-finance/accounts/[id]/amortization/page.tsx`.
 *
 * Layout:
 *  - Header con swatch + nombre + capital pendiente actual.
 *  - 4 KPI cards en grid: cuota, intereses totales, total a pagar,
 *    plazo restante.
 *  - FlatList con todas las filas. Como RN no tiene sticky headers
 *    nativos fáciles, ponemos el header de la tabla justo arriba de
 *    la lista y el ScrollView interno paginea.
 *  - Empty state si scheduleQuery.isError (faltan apr/term/start).
 */
export default function AmortizationScreen() {
  const params = useLocalSearchParams<{ id: string }>();
  const id = params.id;

  const accountQuery = useAccount(id);
  const scheduleQuery = useAmortizationSchedule(id);
  // El cuadro vive en backend pero el "capital pendiente actual" lo
  // sacamos de balances (igual que web). staleTime 60s — si la
  // pantalla viene desde el listado suele estar tibio.
  const balancesQuery = useAccountBalances();

  const account = accountQuery.data;
  const schedule = scheduleQuery.data;

  const balanceItem = useMemo(() => {
    if (!id) return undefined;
    return balancesQuery.data?.items.find((item) => item.account_id === id);
  }, [balancesQuery.data, id]);

  const isMissingFields = scheduleQuery.isError;

  if (!id) {
    return (
      <View style={styles.container}>
        <Stack.Screen options={{ title: 'Cuadro de amortización' }} />
        <Text style={styles.error}>ID de cuenta inválido.</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Stack.Screen options={{ title: 'Cuadro de amortización' }} />
      {accountQuery.isLoading || scheduleQuery.isLoading ? (
        <View style={styles.centerBlock}>
          <Text style={styles.placeholder}>Cargando cuadro…</Text>
        </View>
      ) : isMissingFields ? (
        <EmptyState error={scheduleQuery.error} accountId={id} />
      ) : schedule && account ? (
        <AmortizationContent
          schedule={schedule}
          currency={account.currency}
          accountName={account.name}
          accountColor={account.color}
          accountIcon={account.icon}
          currentBalance={balanceItem?.current_balance ?? null}
          currentBalanceCurrency={balanceItem?.currency ?? null}
        />
      ) : null}
    </View>
  );
}

interface AmortizationContentProps {
  schedule: NonNullable<ReturnType<typeof useAmortizationSchedule>['data']>;
  currency: string;
  accountName: string;
  accountColor: string | null;
  accountIcon: string | null;
  currentBalance: string | null;
  currentBalanceCurrency: string | null;
}

function AmortizationContent({
  schedule,
  currency,
  accountName,
  accountColor,
  accountIcon,
  currentBalance,
  currentBalanceCurrency,
}: AmortizationContentProps) {
  const elapsed = monthsElapsedSince(schedule.start_date, schedule.term_months);
  const remainingMonths = Math.max(0, schedule.term_months - elapsed);
  const aprPercent = (Number(schedule.apr) * 100).toFixed(2);

  // Header arriba (no sticky — RN sticky es costoso), después FlatList
  // con la tabla. Encapsulamos el header en `ListHeaderComponent`
  // para que el scroll incluya KPIs + cabecera de la tabla.
  return (
    <FlatList
      data={schedule.rows}
      keyExtractor={(row: AmortizationRow) => String(row.month)}
      contentContainerStyle={styles.listContent}
      ListHeaderComponent={
        <View style={styles.headerWrap}>
          <View style={styles.headerRow}>
            <AccountSwatch color={accountColor} icon={accountIcon} size={44} />
            <View style={{ flex: 1, minWidth: 0 }}>
              <Text style={styles.headerEyebrow}>
                CUADRO DE AMORTIZACIÓN · LOCAL
              </Text>
              <Text style={styles.headerTitle} numberOfLines={2}>
                {accountName}
              </Text>
              {currentBalance && currentBalanceCurrency ? (
                <Text style={styles.headerSubtitle}>
                  Capital pendiente actual:{' '}
                  <Text style={styles.headerBalance}>
                    {formatAmount(currentBalance, currentBalanceCurrency)}
                  </Text>
                </Text>
              ) : null}
            </View>
          </View>

          <View style={styles.kpiGrid}>
            <KpiCard
              label="Cuota mensual"
              value={formatAmount(schedule.monthly_payment, currency)}
            />
            <KpiCard
              label="Intereses totales"
              value={formatAmount(schedule.total_interest, currency)}
              valueColor={colors.danger}
            />
            <KpiCard
              label="Total a pagar"
              value={formatAmount(schedule.total_paid, currency)}
            />
            <KpiCard
              label="Plazo restante"
              value={formatMonthsAsDuration(remainingMonths)}
              footer={`${schedule.term_months} meses · ${aprPercent}% APR`}
            />
          </View>

          <View style={styles.tableHeaderCard}>
            <View style={styles.tableHeaderLine}>
              <Text style={styles.tableTitle}>
                Tabla completa · {schedule.rows.length} cuotas
              </Text>
              <Text style={styles.tableSubtitle}>
                Inicio: {formatDate(`${schedule.start_date}T00:00:00Z`)}
              </Text>
            </View>
            <View style={styles.tableHeadRow}>
              <Text style={[styles.tableHeadCell, styles.colMonth]}>Mes</Text>
              <Text style={[styles.tableHeadCell, styles.colDate]}>Fecha</Text>
              <Text style={[styles.tableHeadCell, styles.colAmount]}>
                Cuota
              </Text>
              <Text style={[styles.tableHeadCell, styles.colAmount]}>
                Intereses
              </Text>
              <Text style={[styles.tableHeadCell, styles.colAmount]}>
                Principal
              </Text>
              <Text style={[styles.tableHeadCell, styles.colSaldo]}>
                Saldo
              </Text>
            </View>
          </View>
        </View>
      }
      renderItem={({ item }) => <Row row={item} currency={currency} />}
      ItemSeparatorComponent={() => <View style={styles.separator} />}
    />
  );
}

function Row({ row, currency }: { row: AmortizationRow; currency: string }) {
  return (
    <View style={styles.tableRow}>
      <Text style={[styles.tableCell, styles.colMonth]}>{row.month}</Text>
      <Text style={[styles.tableCell, styles.colDate]} numberOfLines={1}>
        {formatDate(`${row.due_date}T00:00:00Z`)}
      </Text>
      <Text style={[styles.tableCell, styles.colAmount]} numberOfLines={1}>
        {formatAmount(row.payment, currency)}
      </Text>
      <Text
        style={[styles.tableCell, styles.colAmount, { color: colors.danger }]}
        numberOfLines={1}
      >
        {formatAmount(row.interest, currency)}
      </Text>
      <Text style={[styles.tableCell, styles.colAmount]} numberOfLines={1}>
        {formatAmount(row.principal, currency)}
      </Text>
      <Text style={[styles.tableCell, styles.colSaldo]} numberOfLines={1}>
        {formatAmount(row.remaining_balance, currency)}
      </Text>
    </View>
  );
}

function KpiCard({
  label,
  value,
  valueColor,
  footer,
}: {
  label: string;
  value: string;
  valueColor?: string;
  footer?: string;
}) {
  return (
    <View style={styles.kpi}>
      <Text style={styles.kpiLabel}>{label}</Text>
      <Text
        style={[styles.kpiValue, { color: valueColor ?? colors.text }]}
        numberOfLines={1}
        adjustsFontSizeToFit
      >
        {value}
      </Text>
      {footer ? <Text style={styles.kpiFooter}>{footer}</Text> : null}
    </View>
  );
}

function EmptyState({
  error,
  accountId,
}: {
  error: unknown;
  accountId: string;
}) {
  return (
    <View style={styles.emptyWrap}>
      <View style={styles.emptyCard}>
        <Text style={styles.emptyTitle}>Faltan datos para calcular el cuadro</Text>
        <Text style={styles.emptyDescription}>
          Para generar el cuadro francés necesitamos el APR anual, el plazo
          en meses y la fecha de inicio del préstamo. Edita la cuenta desde
          la pantalla Cuentas y rellena los tres campos.
        </Text>
        {error ? (
          <Text style={styles.emptyMeta}>
            {formatApiError(error, 'Detalle del backend')} ·{' '}
            <Text style={styles.emptyMetaMono}>{accountId}</Text>
          </Text>
        ) : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  centerBlock: { padding: spacing.lg },
  placeholder: { color: colors.textMuted, fontSize: fontSize.sm },
  error: { color: colors.danger, padding: spacing.lg },
  listContent: { paddingBottom: spacing.xxl },
  headerWrap: {
    padding: spacing.md,
    gap: spacing.md,
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
  },
  headerEyebrow: {
    fontSize: 11,
    fontWeight: fontWeight.semibold,
    color: colors.primary,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
    marginBottom: spacing.xs,
  },
  headerTitle: {
    fontSize: fontSize.xl,
    fontWeight: fontWeight.bold,
    color: colors.text,
    lineHeight: fontSize.xl + 4,
  },
  headerSubtitle: {
    marginTop: spacing.xs,
    fontSize: fontSize.sm,
    color: colors.textMuted,
  },
  headerBalance: {
    color: colors.danger,
    fontWeight: fontWeight.semibold,
  },
  kpiGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
  },
  kpi: {
    flexBasis: '48%',
    flexGrow: 1,
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.md,
    padding: spacing.md,
  },
  kpiLabel: {
    fontSize: fontSize.xs,
    fontWeight: fontWeight.medium,
    color: colors.textMuted,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  kpiValue: {
    fontSize: fontSize.lg,
    fontWeight: fontWeight.bold,
    marginTop: spacing.xs,
  },
  kpiFooter: {
    marginTop: spacing.xs,
    fontSize: fontSize.xs,
    color: colors.textSubtle,
  },
  tableHeaderCard: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderTopLeftRadius: radius.md,
    borderTopRightRadius: radius.md,
    overflow: 'hidden',
  },
  tableHeaderLine: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    flexWrap: 'wrap',
    gap: spacing.xs,
  },
  tableTitle: {
    fontSize: fontSize.sm,
    fontWeight: fontWeight.semibold,
    color: colors.text,
  },
  tableSubtitle: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
  },
  tableHeadRow: {
    flexDirection: 'row',
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    backgroundColor: colors.surfaceMuted,
  },
  tableHeadCell: {
    fontSize: 10,
    fontWeight: fontWeight.semibold,
    color: colors.textMuted,
    textTransform: 'uppercase',
    letterSpacing: 0.4,
  },
  tableRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: spacing.sm + spacing.md,
    paddingVertical: spacing.sm,
    backgroundColor: colors.surface,
    marginHorizontal: spacing.md,
    borderLeftWidth: 1,
    borderRightWidth: 1,
    borderColor: colors.border,
  },
  tableCell: {
    fontSize: fontSize.xs,
    color: colors.text,
  },
  colMonth: { width: 28 },
  colDate: { width: 70 },
  colAmount: { flex: 1, textAlign: 'right' },
  colSaldo: { flex: 1.1, textAlign: 'right' },
  separator: {
    height: 1,
    backgroundColor: colors.border,
    marginHorizontal: spacing.md,
  },
  emptyWrap: {
    padding: spacing.md,
  },
  emptyCard: {
    padding: spacing.lg,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    borderStyle: 'dashed',
    backgroundColor: colors.surfaceMuted,
    alignItems: 'center',
    gap: spacing.sm,
  },
  emptyTitle: {
    fontSize: fontSize.lg,
    fontWeight: fontWeight.semibold,
    color: colors.text,
    textAlign: 'center',
  },
  emptyDescription: {
    fontSize: fontSize.sm,
    color: colors.textMuted,
    textAlign: 'center',
    lineHeight: 18,
  },
  emptyMeta: {
    marginTop: spacing.sm,
    fontSize: fontSize.xs,
    color: colors.textSubtle,
    textAlign: 'center',
  },
  emptyMetaMono: {
    fontFamily: 'monospace',
  },
});
