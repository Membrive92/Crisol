import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { usePortfolioSummary } from '@crisol/services';
import type { PositionSummary } from '@crisol/types';
import { colors, fontSize, fontWeight, radius, spacing, formatAmount } from '@crisol/ui';

import { AddLotForm } from '@/components/investment/add-lot-form';

export default function PortfolioScreen() {
  const summary = usePortfolioSummary();
  const data = summary.data;
  const [adding, setAdding] = useState(false);
  // Los agregados van en la divisa BASE que declara el backend. Antes se
  // formateaban con la divisa de la primera posición, lo que etiquetaba una
  // suma de divisas mezcladas como si fuera toda de una (PHASE-44.11.E).
  const base = data?.base_currency ?? 'EUR';

  return (
    <ScrollView contentContainerStyle={styles.container}>
      {data && !data.pricing_enabled ? (
        <Text style={styles.note}>
          Proveedor de cotizaciones desactivado: posiciones a coste, sin valor de mercado.
        </Text>
      ) : null}

      <View style={styles.kpiRow}>
        <Kpi
          label={`Valor mercado (${base})`}
          value={data ? formatAmount(data.total_market_value_base, base) : '—'}
        />
        <Kpi
          label={`P&L latente (${base})`}
          value={data ? formatAmount(data.total_unrealized_pnl_base, base) : '—'}
        />
      </View>
      <View style={styles.kpiRow}>
        <Kpi label="P&L realizado" value={data ? formatAmount(data.total_realized_pnl, base) : '—'} />
        <Kpi label="Dividendos" value={data ? formatAmount(data.total_dividends_net, base) : '—'} />
      </View>

      {data && data.unquoted_count > 0 ? (
        <Text style={styles.note}>
          {data.unquoted_count === 1
            ? '1 posición fuera de los totales'
            : `${data.unquoted_count} posiciones fuera de los totales`}
          : cada una indica su motivo.
        </Text>
      ) : null}

      {adding ? (
        <View style={styles.card}>
          <View style={styles.rowBetween}>
            <Text style={styles.value}>Nueva compra</Text>
            <Pressable onPress={() => setAdding(false)}>
              <Text style={styles.link}>cancelar</Text>
            </Pressable>
          </View>
          <AddLotForm
            onDone={() => {
              setAdding(false);
              void summary.refetch();
            }}
          />
        </View>
      ) : (
        <Pressable onPress={() => setAdding(true)} style={styles.primaryBtn}>
          <Text style={styles.primaryBtnText}>Añadir compra</Text>
        </Pressable>
      )}

      {summary.isLoading ? (
        <Text style={styles.muted}>Cargando cartera…</Text>
      ) : (data?.positions.length ?? 0) === 0 ? (
        // Ya no dice «añádelas desde la web»: el flujo está aquí (PHASE-44.8 E4).
        <Text style={styles.muted}>Sin posiciones todavía.</Text>
      ) : (
        data?.positions.map((p) => <PositionRow key={p.security_id} position={p} />)
      )}
    </ScrollView>
  );
}

function PositionRow({ position: p }: { position: PositionSummary }) {
  const unrealized = p.unrealized_pnl;
  const color = unrealized === null ? colors.textMuted : Number(unrealized) >= 0 ? colors.success : colors.danger;
  // La divisa del precio la declara el proveedor (PHASE-44.11 D4).
  const priceCurrency = p.quote_currency ?? p.currency;
  return (
    <View style={styles.card}>
      <View style={styles.rowBetween}>
        <Text style={styles.ticker}>{p.ticker}</Text>
        <Text style={styles.value}>
          {p.market_value ? formatAmount(p.market_value, priceCurrency) : 'sin valorar'}
        </Text>
      </View>
      <View style={styles.rowBetween}>
        <Text style={styles.muted}>
          {Number(p.quantity).toLocaleString('es-ES', { maximumFractionDigits: 4 })} ·{' '}
          {p.avg_cost ? formatAmount(p.avg_cost, p.currency) : '—'}
        </Text>
        <Text style={[styles.muted, { color }]}>
          {unrealized ? formatAmount(unrealized, priceCurrency) : '—'}
        </Text>
      </View>
      {p.exclusion_reason ? <Text style={styles.note}>{p.exclusion_reason}</Text> : null}
      {p.currency_mismatch ? (
        <Text style={styles.warn}>
          El catálogo dice {p.currency} y el proveedor devuelve {p.quote_currency}; se valora con la
          del proveedor.
        </Text>
      ) : null}
      {p.quote_stale ? <Text style={styles.note}>Última cotización guardada (no refrescada).</Text> : null}
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
  warn: { color: colors.warning, fontSize: fontSize.xs },
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
  link: { color: colors.primary, fontSize: fontSize.sm },
  primaryBtn: {
    backgroundColor: colors.primary,
    borderRadius: radius.md,
    paddingVertical: spacing.sm,
    alignItems: 'center',
  },
  primaryBtnText: {
    color: colors.onPrimary,
    fontSize: fontSize.sm,
    fontWeight: fontWeight.semibold,
  },
});
