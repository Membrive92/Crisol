import { ScrollView, StyleSheet, Text, View } from 'react-native';

import { usePortfolioSummary } from '@crisol/services';
import type { PositionSummary } from '@crisol/types';
import { colors, fontSize, fontWeight, radius, spacing, formatAmount } from '@crisol/ui';

export default function PortfolioScreen() {
  const summary = usePortfolioSummary();
  const data = summary.data;
  const currency = data?.positions.find((p) => p.currency)?.currency ?? 'USD';

  return (
    <ScrollView contentContainerStyle={styles.container}>
      {!data?.pricing_enabled ? (
        <Text style={styles.note}>
          Cotizaciones desactivadas (sin API key): posiciones a coste, sin valor de mercado.
        </Text>
      ) : null}

      <View style={styles.kpiRow}>
        <Kpi label="Valor mercado" value={data ? formatAmount(data.total_market_value, currency) : '—'} />
        <Kpi label="P&L latente" value={data ? formatAmount(data.total_unrealized_pnl, currency) : '—'} />
      </View>
      <View style={styles.kpiRow}>
        <Kpi label="P&L realizado" value={data ? formatAmount(data.total_realized_pnl, currency) : '—'} />
        <Kpi label="Dividendos" value={data ? formatAmount(data.total_dividends_net, currency) : '—'} />
      </View>

      {summary.isLoading ? (
        <Text style={styles.muted}>Cargando cartera…</Text>
      ) : (data?.positions.length ?? 0) === 0 ? (
        <Text style={styles.muted}>Sin posiciones todavía. Añádelas desde la web.</Text>
      ) : (
        data?.positions.map((p) => <PositionRow key={p.security_id} position={p} />)
      )}
    </ScrollView>
  );
}

function PositionRow({ position: p }: { position: PositionSummary }) {
  const unrealized = p.unrealized_pnl;
  const color = unrealized === null ? colors.textMuted : Number(unrealized) >= 0 ? colors.success : colors.danger;
  return (
    <View style={styles.card}>
      <View style={styles.rowBetween}>
        <Text style={styles.ticker}>{p.ticker}</Text>
        <Text style={styles.value}>
          {p.market_value ? formatAmount(p.market_value, p.currency) : 'sin cotización'}
        </Text>
      </View>
      <View style={styles.rowBetween}>
        <Text style={styles.muted}>
          {Number(p.quantity).toLocaleString('es-ES', { maximumFractionDigits: 4 })} ·{' '}
          {p.avg_cost ? formatAmount(p.avg_cost, p.currency) : '—'}
        </Text>
        <Text style={[styles.muted, { color }]}>
          {unrealized ? formatAmount(unrealized, p.currency) : '—'}
        </Text>
      </View>
    </View>
  );
}

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <View style={[styles.card, styles.kpi]}>
      <Text style={styles.kpiLabel}>{label}</Text>
      <Text style={styles.kpiValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { padding: spacing.md, gap: spacing.sm },
  note: { color: colors.textSubtle, fontSize: fontSize.xs },
  muted: { color: colors.textMuted, fontSize: fontSize.sm },
  kpiRow: { flexDirection: 'row', gap: spacing.sm },
  kpi: { flex: 1 },
  kpiLabel: { color: colors.textMuted, fontSize: fontSize.xs },
  kpiValue: { color: colors.text, fontSize: fontSize.lg, fontWeight: fontWeight.bold },
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    gap: spacing.xs,
  },
  rowBetween: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  ticker: { color: colors.text, fontSize: fontSize.md, fontWeight: fontWeight.bold },
  value: { color: colors.text, fontSize: fontSize.sm, fontWeight: fontWeight.semibold },
});
