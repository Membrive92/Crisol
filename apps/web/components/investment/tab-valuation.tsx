'use client';

import { useState } from 'react';

import { useValuation } from '@crisol/services';
import type { Security, Valuation } from '@crisol/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';

import { Card, CardTitle } from '@/components/ui/card';

import { InlineNotice } from './degraded-panel';
import { formatMetricValue } from '@crisol/ui';
import type { CatalogIndex } from '@crisol/ui';

/**
 * Pestaña de Valoración (PHASE-44.12).
 *
 * Vive SEPARADA del veredicto forense a propósito. «¿Es seguro?» y «¿está
 * cara?» son preguntas distintas: la primera sale de cuentas cerradas y es
 * reproducible; la segunda depende del precio de hoy. Mezclarlas invitaría a
 * leer un «Evitar» del motor forense como si tuviera que ver con lo que cuesta
 * la acción.
 *
 * Por eso tampoco lleva semáforos: sin comparables de sector, un color sería
 * una opinión disfrazada de dato. Se muestra el número; el juicio lo pone quien
 * mira.
 */

// El orden y los acompañantes viven en `@crisol/ui` para que móvil muestre
// exactamente los mismos múltiplos (PHASE-44.8).
import { VALUATION_COMPANIONS as COMPANIONS, VALUATION_ORDER as ORDER } from '@crisol/ui';

export interface TabValuationProps {
  securityId: string;
  security: Security | undefined;
  catalog: CatalogIndex;
}

export function TabValuation({ securityId, security, catalog }: TabValuationProps) {
  const [draft, setDraft] = useState('');
  const [override, setOverride] = useState<string | undefined>(undefined);
  const query = useValuation(securityId, override);
  const data = query.data;

  function applyOverride(event: React.FormEvent) {
    event.preventDefault();
    const trimmed = draft.trim().replace(',', '.');
    setOverride(trimmed === '' ? undefined : trimmed);
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.lg }}>
      <Card>
        <CardTitle size="sm">Precio de referencia</CardTitle>
        <p style={note}>
          Los múltiplos cruzan la cotización con el último ejercicio cerrado. Puedes
          simular otro precio de entrada sin que afecte al análisis forense.
        </p>
        <form onSubmit={applyOverride} style={{ display: 'flex', gap: spacing.sm, marginTop: spacing.md, flexWrap: 'wrap' }}>
          <input
            type="text"
            inputMode="decimal"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder={data?.quote_as_of ? 'Simular otro precio' : 'Introducir precio'}
            aria-label="Precio a simular"
            style={input}
          />
          <button type="submit" style={button}>
            Calcular
          </button>
          {override !== undefined ? (
            <button
              type="button"
              onClick={() => {
                setDraft('');
                setOverride(undefined);
              }}
              style={{ ...button, background: 'transparent', color: colors.textMuted }}
            >
              Volver al precio de mercado
            </button>
          ) : null}
        </form>

        {query.isLoading ? <p style={note}>Consultando la cotización…</p> : null}
        {data ? <ProviderLamp status={data.provider_status} /> : null}
        {data ? <PriceSummary data={data} /> : null}
      </Card>

      {data && !data.available ? (
        <InlineNotice>
          {data.reason ?? 'No se pueden calcular los múltiplos para este valor.'}
        </InlineNotice>
      ) : null}

      {data?.available ? (
        <>
          <Card>
            <CardTitle size="sm">Múltiplos</CardTitle>
            <MetricTable
              data={data}
              catalog={catalog}
              keys={[...ORDER]}
              currency={data.statement_currency}
            />
          </Card>

          <Card>
            <CardTitle size="sm">Por acción y rentabilidad</CardTitle>
            <p style={note}>
              Estos dos se emiten aunque salgan negativos: ahí el signo informa en vez de
              engañar. Un valor contable por acción negativo dice algo cierto sobre la
              estructura de capital; un precio/valor contable negativo, no.
            </p>
            <MetricTable
              data={data}
              catalog={catalog}
              keys={[...COMPANIONS]}
              currency={data.statement_currency}
            />
          </Card>
        </>
      ) : null}

      {data?.notes.length ? (
        <Card>
          <CardTitle size="sm">Advertencias</CardTitle>
          <ul style={{ margin: 0, paddingLeft: spacing.lg, color: colors.textMuted, fontSize: fontSize.sm }}>
            {data.notes.map((n) => (
              <li key={n} style={{ marginBottom: spacing.xs }}>
                {n}
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      <Card>
        <CardTitle size="sm">Qué NO dice esta pestaña</CardTitle>
        <ul style={{ margin: 0, paddingLeft: spacing.lg, color: colors.textMuted, fontSize: fontSize.sm }}>
          <li style={{ marginBottom: spacing.xs }}>
            <strong>No hay semáforos.</strong> Un PER de 25× es caro en una eléctrica y
            barato en software. Sin comparables de sector —y no hay fuente gratuita— una
            banda sería una opinión disfrazada de dato.
          </li>
          <li style={{ marginBottom: spacing.xs }}>
            <strong>No entra en el veredicto.</strong> El dictamen forense es book-based
            para poder reejecutarse dando lo mismo. Estos números se mueven con el
            precio, así que se calculan al vuelo y no se guardan.
          </li>
          <li>
            <strong>Sin descuento de dividendos.</strong> El modelo de Gordon necesita
            beta y prima de riesgo, y no hay fuente verificada de ninguna de las dos.
          </li>
        </ul>
      </Card>

      {security?.is_financial ? (
        <InlineNotice>
          En una financiera, «ventas» es margen por intereses y comisiones: el
          precio/ventas no es comparable con el de una empresa industrial.
        </InlineNotice>
      ) : null}
    </div>
  );
}

/**
 * Semáforo del proveedor de cotizaciones.
 *
 * Tres estados y no dos, porque «no lo he preguntado» no es «está bien». Con el
 * TTL en 24 h, la segunda visita del día no consulta a nadie: pintar verde ahí
 * sería afirmar una comprobación que no se ha hecho.
 */
function ProviderLamp({ status }: { status: Valuation['provider_status'] }) {
  const config = {
    live: {
      color: colors.success,
      label: 'Proveedor de cotizaciones en servicio',
      detail: 'Precio pedido y recibido ahora mismo.',
    },
    cached: {
      color: colors.textSubtle,
      label: 'Precio guardado',
      detail:
        'No ha hecho falta consultar al proveedor: la cotización seguía dentro de su ventana de validez.',
    },
    unreachable: {
      color: colors.danger,
      label: 'Proveedor de cotizaciones sin respuesta',
      detail: 'Se muestra el último precio registrado. Los múltiplos usan ese precio.',
    },
  }[status];

  return (
    <div
      role="status"
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: spacing.sm,
        marginTop: spacing.md,
      }}
    >
      <span
        aria-hidden="true"
        style={{
          width: 10,
          height: 10,
          marginTop: 4,
          borderRadius: '50%',
          background: config.color,
          boxShadow: `0 0 0 3px ${config.color}22`,
          flexShrink: 0,
        }}
      />
      <span style={{ fontSize: fontSize.sm, color: colors.text }}>
        {config.label}
        <span style={{ display: 'block', color: colors.textMuted, fontSize: fontSize.xs }}>
          {config.detail}
        </span>
      </span>
    </div>
  );
}

function PriceSummary({ data }: { data: Valuation }) {
  const rows: [string, string][] = [];
  if (data.market_cap) {
    rows.push(['Capitalización', formatBig(data.market_cap, data.statement_currency)]);
  }
  if (data.enterprise_value) {
    rows.push(['Valor de empresa', formatBig(data.enterprise_value, data.statement_currency)]);
  }
  if (data.quote_as_of) rows.push(['Precio del', formatDate(data.quote_as_of)]);
  if (data.fiscal_year_end) rows.push(['Cuentas a', formatDate(data.fiscal_year_end)]);
  if (data.fx_rate && data.fx_as_of) {
    rows.push(['Tipo aplicado', `${data.fx_rate} · ${formatDate(data.fx_as_of)}`]);
  }

  return (
    <div style={{ marginTop: spacing.md, display: 'flex', flexDirection: 'column', gap: spacing.xs }}>
      {data.price_is_override ? (
        <Badge tone={colors.warning}>Precio introducido a mano, no de mercado</Badge>
      ) : null}
      {data.quote_stale && data.provider_status !== 'unreachable' ? (
        <Badge tone={colors.textSubtle}>La cotización ha superado su ventana de validez</Badge>
      ) : null}
      {data.staleness ? (
        <Badge tone={data.staleness === 'stale' ? colors.warning : colors.textSubtle}>
          {data.staleness === 'stale'
            ? 'Las cuentas tienen más de año y medio'
            : 'Las cuentas tienen más de nueve meses'}
        </Badge>
      ) : null}
      <dl style={{ margin: `${spacing.sm}px 0 0`, display: 'grid', gridTemplateColumns: 'auto 1fr', gap: `${spacing.xs}px ${spacing.md}px` }}>
        {rows.map(([label, value]) => (
          <div key={label} style={{ display: 'contents' }}>
            <dt style={{ color: colors.textMuted, fontSize: fontSize.sm }}>{label}</dt>
            <dd style={{ margin: 0, color: colors.text, fontSize: fontSize.sm, fontVariantNumeric: 'tabular-nums' }}>
              {value}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function MetricTable({
  data,
  catalog,
  keys,
  currency,
}: {
  data: Valuation;
  catalog: CatalogIndex;
  keys: string[];
  currency: string | null;
}) {
  const byKey = new Map(data.metrics.map((m) => [m.key, m]));
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: spacing.md, fontSize: fontSize.sm }}>
      <tbody>
        {keys.map((key) => {
          const metric = byKey.get(key);
          const definition = catalog.definition(key);
          if (!metric) return null;
          const isCurrency = definition?.unit === 'currency_per_share';
          return (
            <tr key={key} style={{ borderTop: `1px solid ${colors.border}` }}>
              <td style={{ padding: `${spacing.sm}px 0`, color: colors.text }}>
                {definition?.label ?? key}
                {definition?.note ? (
                  <div style={{ color: colors.textSubtle, fontSize: fontSize.xs, marginTop: 2 }}>
                    {definition.note}
                  </div>
                ) : null}
              </td>
              <td
                style={{
                  padding: `${spacing.sm}px 0`,
                  textAlign: 'right',
                  color: metric.value === null ? colors.textSubtle : colors.text,
                  fontWeight: metric.value === null ? fontWeight.regular : fontWeight.semibold,
                  fontVariantNumeric: 'tabular-nums',
                  whiteSpace: 'nowrap',
                }}
              >
                {metric.value === null ? (
                  <span style={{ fontSize: fontSize.xs }}>no computable</span>
                ) : (
                  <>
                    {formatMetricValue(metric.value, definition?.unit)}
                    {isCurrency && currency ? ` ${currency}` : ''}
                  </>
                )}
              </td>
            </tr>
          );
        })}
        {keys.map((key) => {
          const metric = byKey.get(key);
          if (!metric?.reason) return null;
          return (
            <tr key={`${key}-reason`}>
              <td colSpan={2} style={{ padding: `0 0 ${spacing.sm}px`, color: colors.textMuted, fontSize: fontSize.xs }}>
                {metric.reason}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function Badge({ children, tone }: { children: React.ReactNode; tone: string }) {
  return (
    <span
      style={{
        alignSelf: 'flex-start',
        padding: `2px ${spacing.sm}px`,
        borderRadius: radius.sm,
        border: `1px solid ${tone}`,
        color: tone,
        fontSize: fontSize.xs,
      }}
    >
      {children}
    </span>
  );
}

/** Importes grandes: en millones, que es como se leen las cuentas. */
function formatBig(value: string, currency: string | null): string {
  const n = Number(value);
  if (!Number.isFinite(n)) return '—';
  const millions = n / 1_000_000;
  return `${millions.toLocaleString('es-ES', { maximumFractionDigits: 0 })} M${currency ? ` ${currency}` : ''}`;
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString('es-ES');
}

const note: React.CSSProperties = {
  margin: `${spacing.xs}px 0 0`,
  color: colors.textMuted,
  fontSize: fontSize.sm,
};

const input: React.CSSProperties = {
  flex: '1 1 180px',
  minWidth: 140,
  padding: `${spacing.xs}px ${spacing.sm}px`,
  borderRadius: radius.sm,
  border: `1px solid ${colors.border}`,
  background: colors.surface,
  color: colors.text,
  fontSize: fontSize.sm,
};

const button: React.CSSProperties = {
  padding: `${spacing.xs}px ${spacing.md}px`,
  borderRadius: radius.sm,
  border: `1px solid ${colors.border}`,
  background: colors.surface,
  color: colors.text,
  fontSize: fontSize.sm,
  cursor: 'pointer',
};
