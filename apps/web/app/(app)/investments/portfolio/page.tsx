'use client';

import { useState } from 'react';

import { usePortfolioSummary, useRefreshPricing } from '@crisol/services';
import type { PositionSummary } from '@crisol/types';
import { colors, fontSize, fontWeight, formatAmount, layout, radius, spacing } from '@crisol/ui';

import { AddLotForm } from '@/components/investment/add-lot-form';
import { Card, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

export default function PortfolioPage() {
  const summary = usePortfolioSummary();
  const refresh = useRefreshPricing();
  const [showForm, setShowForm] = useState(false);

  const data = summary.data;
  // Los agregados van en la divisa BASE que declara el backend. Antes se
  // formateaban con la divisa de la primera posición, lo que etiquetaba una
  // suma de divisas mezcladas como si fuera toda de una (PHASE-44.11.E).
  const base = data?.base_currency ?? 'EUR';

  return (
    <div
      style={{
        maxWidth: layout.pageWide,
        margin: '0 auto',
        padding: spacing.lg,
        display: 'flex',
        flexDirection: 'column',
        gap: spacing.lg,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: spacing.md, flexWrap: 'wrap' }}>
        <h1 style={{ margin: 0, fontSize: fontSize.xxl, fontWeight: fontWeight.bold, color: colors.text }}>
          Cartera
        </h1>
        <div style={{ display: 'flex', gap: spacing.sm }}>
          <Button variant="secondary" onClick={() => setShowForm((v) => !v)}>
            {showForm ? 'Cerrar' : 'Añadir compra'}
          </Button>
          {data?.pricing_enabled ? (
            <Button
              variant="secondary"
              onClick={() => void refresh.mutateAsync({})}
              disabled={refresh.isPending}
            >
              {refresh.isPending ? 'Actualizando…' : 'Actualizar precios'}
            </Button>
          ) : null}
        </div>
      </div>

      {showForm ? (
        <Card>
          <CardTitle size="sm">Nueva compra</CardTitle>
          <div style={{ marginTop: spacing.md }}>
            <AddLotForm onDone={() => setShowForm(false)} />
          </div>
        </Card>
      ) : null}

      {data && !data.pricing_enabled ? (
        <p style={{ color: colors.textSubtle, fontSize: fontSize.xs, margin: 0 }}>
          El proveedor de cotizaciones está desactivado: las posiciones se muestran a coste y sin
          valor de mercado.
        </p>
      ) : null}

      <div style={{ display: 'grid', gap: spacing.md, gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))' }}>
        <Kpi
          label={`Valor de mercado (${base})`}
          value={data ? formatAmount(data.total_market_value_base, base) : '—'}
        />
        <Kpi
          label={`P&L latente (${base})`}
          value={data ? formatAmount(data.total_unrealized_pnl_base, base) : '—'}
        />
        <Kpi label="P&L realizado" value={data ? formatAmount(data.total_realized_pnl, base) : '—'} />
        <Kpi label="Dividendos (neto)" value={data ? formatAmount(data.total_dividends_net, base) : '—'} />
      </div>

      {data && data.currency_exposure.length > 1 ? (
        <p style={{ color: colors.textMuted, fontSize: fontSize.xs, margin: 0 }}>
          Exposición por divisa:{' '}
          {data.currency_exposure
            .map((row) => `${row.currency} ${(Number(row.weight_pct) * 100).toFixed(1)}%`)
            .join(' · ')}
        </p>
      ) : null}

      {data && data.unquoted_count > 0 ? (
        <p style={{ color: colors.textSubtle, fontSize: fontSize.xs, margin: 0 }}>
          {data.unquoted_count === 1
            ? '1 posición queda fuera de los totales'
            : `${data.unquoted_count} posiciones quedan fuera de los totales`}
          : no se valoran a coste como sustituto, y cada una indica su motivo.
        </p>
      ) : null}

      <Card style={{ padding: 0, overflow: 'hidden' }}>
        {summary.isLoading ? (
          <p style={{ padding: spacing.lg, color: colors.textMuted }}>Cargando cartera…</p>
        ) : (data?.positions.length ?? 0) === 0 ? (
          <p style={{ padding: spacing.lg, color: colors.textMuted }}>
            Sin posiciones todavía. Añade tu primera compra.
          </p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', minWidth: 720, borderCollapse: 'collapse', fontSize: fontSize.sm }}>
              <thead>
                <tr style={{ textAlign: 'right', color: colors.textMuted }}>
                  <th style={{ ...th, textAlign: 'left' }}>Valor</th>
                  <th style={th}>Cantidad</th>
                  <th style={th}>Coste medio</th>
                  <th style={th}>Precio</th>
                  <th style={th}>Valor mercado</th>
                  <th style={th}>P&L latente</th>
                  <th style={th}>Peso</th>
                </tr>
              </thead>
              <tbody>
                {data?.positions.map((p) => (
                  <PositionRow key={p.security_id} position={p} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

function PositionRow({ position: p }: { position: PositionSummary }) {
  const unrealized = p.unrealized_pnl;
  const unrealizedColor =
    unrealized === null ? colors.textMuted : Number(unrealized) >= 0 ? colors.success : colors.danger;
  // La divisa del precio la declara el proveedor; la del catálogo sólo se usa
  // si no la declaró. Formatear con la del catálogo cuando discrepan pintaría
  // libras donde el mercado dio dólares (PHASE-44.11 D4).
  const priceCurrency = p.quote_currency ?? p.currency;
  return (
    <tr style={{ borderTop: `1px solid ${colors.border}` }}>
      <td style={{ ...td, textAlign: 'left' }}>
        <strong style={{ color: colors.text }}>{p.ticker}</strong>{' '}
        <span style={{ color: colors.textMuted }}>{p.name}</span>
        {p.currency_mismatch ? (
          <Badge
            tone={colors.warning}
            title={`El catálogo dice ${p.currency} y el proveedor devuelve ${p.quote_currency}. Se valora con la del proveedor.`}
          >
            divisa {p.quote_currency}
          </Badge>
        ) : null}
        {p.quote_stale ? (
          <Badge tone={colors.textSubtle} title="No se ha podido refrescar: es la última cotización guardada.">
            precio antiguo
          </Badge>
        ) : null}
      </td>
      <td style={num}>{Number(p.quantity).toLocaleString('es-ES', { maximumFractionDigits: 4 })}</td>
      <td style={num}>{p.avg_cost ? formatAmount(p.avg_cost, p.currency) : '—'}</td>
      <td style={num}>{p.last_price ? formatAmount(p.last_price, priceCurrency) : '—'}</td>
      <td style={num}>
        {p.market_value ? (
          formatAmount(p.market_value, priceCurrency)
        ) : (
          <span style={{ color: colors.textSubtle, fontSize: fontSize.xs }}>
            {p.exclusion_reason ?? 'sin cotización'}
          </span>
        )}
      </td>
      <td style={{ ...num, color: unrealizedColor }}>
        {unrealized ? formatAmount(unrealized, priceCurrency) : '—'}
      </td>
      <td style={num}>{p.weight_pct ? `${(Number(p.weight_pct) * 100).toFixed(1)}%` : '—'}</td>
    </tr>
  );
}

function Badge({
  children,
  tone,
  title,
}: {
  children: React.ReactNode;
  tone: string;
  title: string;
}) {
  return (
    <span
      title={title}
      style={{
        marginLeft: spacing.xs,
        padding: `1px ${spacing.xs}px`,
        borderRadius: radius.sm,
        border: `1px solid ${tone}`,
        color: tone,
        fontSize: fontSize.xs,
        whiteSpace: 'nowrap',
      }}
    >
      {children}
    </span>
  );
}

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <Card compact style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <span style={{ color: colors.textMuted, fontSize: fontSize.xs }}>{label}</span>
      <span style={{ color: colors.text, fontSize: fontSize.lg, fontWeight: fontWeight.bold, fontVariantNumeric: 'tabular-nums' }}>
        {value}
      </span>
    </Card>
  );
}

const th: React.CSSProperties = { padding: `${spacing.sm}px ${spacing.md}px`, fontWeight: 600, textAlign: 'right' };
const td: React.CSSProperties = { padding: `${spacing.sm}px ${spacing.md}px` };
const num: React.CSSProperties = { ...td, textAlign: 'right', fontVariantNumeric: 'tabular-nums', color: colors.text };
