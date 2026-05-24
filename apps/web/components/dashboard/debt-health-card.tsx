'use client';

import { useDebtHealth } from '@crisol/services';
import { useCurrencyStore } from '@crisol/store';
import type { DtiStatus } from '@crisol/types';
import {
  colors,
  fontSize,
  fontWeight,
  formatAmount,
  radius,
  spacing,
} from '@crisol/ui';

import { Card } from '@/components/ui/card';
import { HeartPulseIcon } from '@/components/ui/icons';

/**
 * Mapea el estado del ratio DTI a un par fondo + texto coherente con
 * la paleta semántica existente.
 */
function dtiStatusColors(status: DtiStatus): { bg: string; fg: string; label: string } {
  switch (status) {
    case 'healthy':
      return { bg: colors.successSoft, fg: colors.success, label: 'Saludable' };
    case 'caution':
      return { bg: colors.warningSoft, fg: colors.warning, label: 'Atención' };
    case 'stressed':
      return { bg: colors.dangerSoft, fg: colors.danger, label: 'Estresado' };
    case 'unknown':
    default:
      return { bg: colors.surfaceMuted, fg: colors.textMuted, label: 'Sin datos' };
  }
}

/**
 * Formatea un número de meses en "X años Y meses" para legibilidad
 * (los meses sueltos por debajo de 12 quedan tal cual).
 */
function formatMonths(months: number | null): string {
  if (months === null || months <= 0) return '—';
  const years = Math.floor(months / 12);
  const remainder = months - years * 12;
  if (years === 0) return `${remainder} ${remainder === 1 ? 'mes' : 'meses'}`;
  if (remainder === 0) return `${years} ${years === 1 ? 'año' : 'años'}`;
  return `${years}a ${remainder}m`;
}

/**
 * Card de salud financiera (PHASE-22). Muestra:
 * - Patrimonio neto (assets - liabilities) en grande.
 * - Sub-row con assets / liabilities / net worth.
 * - Grid de KPIs: DTI (badge tonal), cuota mensual, APR ponderado,
 *   tiempo para saldar, intereses YTD, % en deuda.
 *
 * Estado vacío: si el usuario no tiene liabilities (`total_liabilities = 0`)
 * se sustituye el grid por un mensaje "Sin deudas registradas".
 */
export function DebtHealthCard() {
  const { data, isLoading, isError } = useDebtHealth();
  const includeDebt = useCurrencyStore((s) => s.includeDebtInNetWorth);

  if (isLoading) {
    return (
      <Card style={{ padding: spacing.md }}>
        <p style={{ margin: 0, color: colors.textMuted, fontSize: fontSize.sm }}>
          Cargando salud financiera…
        </p>
      </Card>
    );
  }

  if (isError || !data) {
    return (
      <Card style={{ padding: spacing.md }}>
        <p style={{ margin: 0, color: colors.danger, fontSize: fontSize.sm }}>
          Error cargando indicadores de deuda.
        </p>
      </Card>
    );
  }

  const totalLiabilitiesNum = Number(data.total_liabilities);
  const hasDebt = totalLiabilitiesNum > 0;
  // Cuando el toggle "Incluir deuda" está OFF, la cifra grande pasa a
  // ser sólo activos. El desglose Activos/Pasivos se mantiene siempre
  // para que el usuario no pierda contexto de lo que está ignorando.
  const displayWorthValue = includeDebt ? data.net_worth : data.total_assets;
  const displayWorthNum = Number(displayWorthValue);
  const netWorthColor = displayWorthNum < 0 ? colors.danger : colors.text;

  const dtiTone = dtiStatusColors(data.dti_status);
  const dtiPercent = data.dti_ratio !== null ? (data.dti_ratio * 100).toFixed(1) : null;
  const aprPercent =
    data.weighted_apr !== null ? (data.weighted_apr * 100).toFixed(2) : null;
  const debtToAssetsPercent =
    data.debt_to_assets_ratio !== null
      ? (data.debt_to_assets_ratio * 100).toFixed(1)
      : null;

  return (
    <Card
      style={{
        padding: spacing.md,
        display: 'flex',
        flexDirection: 'column',
        gap: spacing.md,
      }}
    >
      <header
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: spacing.sm,
        }}
      >
        <div
          aria-hidden
          style={{
            width: 36,
            height: 36,
            borderRadius: '50%',
            backgroundColor: colors.primarySoft,
            color: colors.primary,
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            flex: '0 0 auto',
          }}
        >
          <HeartPulseIcon size={18} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: spacing.xs,
              fontSize: 11,
              fontWeight: fontWeight.semibold,
              color: colors.textMuted,
              textTransform: 'uppercase',
              letterSpacing: '0.04em',
            }}
          >
            Salud financiera
            {!includeDebt && hasDebt ? (
              <span
                style={{
                  fontSize: 10,
                  color: colors.textMuted,
                  backgroundColor: colors.surfaceMuted,
                  padding: '1px 6px',
                  borderRadius: radius.sm,
                  letterSpacing: '0.04em',
                }}
              >
                Sin deuda
              </span>
            ) : null}
          </span>
          <span
            style={{
              fontSize: fontSize.xl,
              fontWeight: fontWeight.bold,
              color: netWorthColor,
              fontVariantNumeric: 'tabular-nums',
              letterSpacing: '-0.01em',
              lineHeight: 1.1,
              display: 'block',
            }}
          >
            {formatAmount(displayWorthValue, data.reference_currency)}
          </span>
        </div>
      </header>

      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: spacing.md,
          fontSize: fontSize.sm,
        }}
      >
        <SubtotalRow
          label="Activos"
          value={formatAmount(data.total_assets, data.reference_currency)}
          color={colors.income}
        />
        <SubtotalRow
          label="Pasivos"
          value={`-${formatAmount(data.total_liabilities, data.reference_currency)}`}
          color={colors.danger}
        />
      </div>

      {hasDebt ? (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
            gap: spacing.sm,
            borderTop: `1px solid ${colors.border}`,
            paddingTop: spacing.md,
          }}
        >
          <Metric
            label="DTI"
            value={dtiPercent !== null ? `${dtiPercent}%` : '—'}
            badge={{
              label: dtiTone.label,
              bg: dtiTone.bg,
              fg: dtiTone.fg,
            }}
          />
          <Metric
            label="Cuota mensual"
            value={formatAmount(data.monthly_debt_payment, data.reference_currency)}
          />
          <Metric
            label="APR medio"
            value={aprPercent !== null ? `${aprPercent}%` : '—'}
          />
          <Metric
            label="Tiempo para saldar"
            value={formatMonths(data.time_to_payoff_months)}
          />
          <Metric
            label="Intereses YTD"
            value={formatAmount(data.interest_paid_ytd, data.reference_currency)}
            valueColor={colors.danger}
          />
          <Metric
            label="% en deuda"
            value={debtToAssetsPercent !== null ? `${debtToAssetsPercent}%` : '—'}
          />
        </div>
      ) : (
        <div
          style={{
            padding: spacing.md,
            borderTop: `1px solid ${colors.border}`,
            textAlign: 'center',
          }}
        >
          <p
            style={{
              margin: 0,
              fontSize: fontSize.sm,
              color: colors.textMuted,
              lineHeight: 1.5,
            }}
          >
            Sin deudas registradas. Cuando añadas una tarjeta, préstamo o
            hipoteca verás aquí ratios de salud financiera y proyección
            de pago.
          </p>
        </div>
      )}
    </Card>
  );
}

function SubtotalRow({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color: string;
}) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'baseline', gap: 4 }}>
      <span
        style={{
          fontSize: fontSize.xs,
          color: colors.textMuted,
          fontWeight: fontWeight.medium,
        }}
      >
        {label}:
      </span>
      <span
        style={{
          fontWeight: fontWeight.semibold,
          color,
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        {value}
      </span>
    </span>
  );
}

function Metric({
  label,
  value,
  valueColor,
  badge,
}: {
  label: string;
  value: string;
  valueColor?: string;
  badge?: { label: string; bg: string; fg: string };
}) {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 2,
      }}
    >
      <span
        style={{
          fontSize: 11,
          fontWeight: fontWeight.medium,
          color: colors.textMuted,
          textTransform: 'uppercase',
          letterSpacing: '0.04em',
        }}
      >
        {label}
      </span>
      <span
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: spacing.xs,
          flexWrap: 'wrap',
        }}
      >
        <span
          style={{
            fontSize: fontSize.md,
            fontWeight: fontWeight.semibold,
            color: valueColor ?? colors.text,
            fontVariantNumeric: 'tabular-nums',
          }}
        >
          {value}
        </span>
        {badge ? (
          <span
            style={{
              fontSize: 10,
              fontWeight: fontWeight.semibold,
              color: badge.fg,
              backgroundColor: badge.bg,
              padding: '1px 6px',
              borderRadius: radius.sm,
              letterSpacing: '0.04em',
              textTransform: 'uppercase',
            }}
          >
            {badge.label}
          </span>
        ) : null}
      </span>
    </div>
  );
}
