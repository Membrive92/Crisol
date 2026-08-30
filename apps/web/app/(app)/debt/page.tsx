'use client';

import Link from 'next/link';
import dynamic from 'next/dynamic';
import { useEffect, useMemo, useRef, useState } from 'react';

import {
  cycleAnchorContaining,
  cycleDaysForAnchor,
  periodLabel,
  useAccountBalances,
  useDebtCategorySummary,
  useDebtHealth,
  useDebtHistory,
  useMe,
  boundsForUserPeriod,
  cycleDayForPeriod,
} from '@crisol/services';
import { useCurrencyStore } from '@crisol/store';
import type { DebtHealthKpis, DebtTimeRange, PeriodKey } from '@crisol/types';
import {
  colors,
  fontSize,
  fontWeight,
  formatAmount,
  layout,
  radius,
  spacing,
} from '@crisol/ui';

import {
} from '@/components/analysis/stitch-period-toggle';
import { DebtList } from '@/components/debt/debt-list';
import { todayDayStr } from '@/components/ui/date-picker';
import { DebtMovementsCard } from '@/components/debt/debt-movements-card';
import { EffortRatioSection } from '@/components/debt/effort-ratio-section';
import { PaymentsSummaryCard } from '@/components/debt/payments-summary-card';
import { PeriodNavigator } from '@/components/debt/period-navigator';
import { RecurringQuotasList } from '@/components/debt/recurring-quotas-list';
import { ErrorState } from '@/components/ui/error-state';
import { InfoTooltip } from '@/components/ui/info-tooltip';
import { Skeleton } from '@/components/ui/skeleton';

// AUDIT-2026-05: charts con recharts en chunk diferido (ssr:false).
const DebtCompositionDonut = dynamic(
  () => import('@/components/debt/debt-composition-donut').then((m) => m.DebtCompositionDonut),
  { ssr: false, loading: () => <Skeleton height={280} /> },
);
const DebtMonthlyEvolution = dynamic(
  () => import('@/components/debt/debt-monthly-evolution').then((m) => m.DebtMonthlyEvolution),
  { ssr: false, loading: () => <Skeleton height={280} /> },
);
const DebtDailyEvolution = dynamic(
  () => import('@/components/debt/debt-daily-evolution').then((m) => m.DebtDailyEvolution),
  { ssr: false, loading: () => <Skeleton height={280} /> },
);
const DebtTrendChart = dynamic(
  () => import('@/components/debt/debt-trend-chart').then((m) => m.DebtTrendChart),
  { ssr: false, loading: () => <Skeleton height={280} /> },
);

/**
 * Página `/debt` rediseñada en PHASE-30.3.
 *
 * Capa 1 (flujo de categorías) primero, sin requerir liability
 * accounts: tasa de esfuerzo, pagos a deuda en el rango, composición
 * por tipo, evolución mensual y cuotas recurrentes detectadas.
 *
 * Capa 2 (contratos concretos) abajo: lista de liabilities con sus
 * cuotas + chart de evolución del saldo. Empty state pide vincular
 * cuando hay cuotas recurrentes pero ningún liability declarado.
 */
/** PHASE-41 — etiqueta corta `dd/mm – dd/mm` del rango libre para el título. */
function formatRangeLabel(from: string | null, to: string | null): string {
  if (!(from && to)) return 'Rango';
  const short = (d: string): string => {
    const [, mo, da] = d.split('-');
    return `${da}/${mo}`;
  };
  return `${short(from)} – ${short(to)}`;
}

export default function DebtPage() {
  // C3a — El estado es `PeriodKey` (vocabulario de la UI, con `cycle`). La API
  // de deuda sólo entiende `month|year|custom`, así que el ciclo se le manda
  // como rango libre con sus dos fechas: `apiRange`/`cycleDays`, más abajo.
  const [range, setRange] = useState<PeriodKey>('year');
  // PHASE-30.8 — Mes ancla `YYYY-MM` del período mostrado. Por defecto
  // el mes en curso → período actual (comportamiento previo). El
  // `PeriodNavigator` lo mueve (limitado a los meses con datos).
  const [anchorMonth, setAnchorMonth] = useState(() => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
  });
  // PHASE-41 — rango libre (`range='custom'`): day-strings `YYYY-MM-DD`. Se
  // siembran desde el período actual al conmutar a "Personalizado" para que
  // los date-pickers no salgan vacíos.
  const [customFrom, setCustomFrom] = useState<string | null>(null);

  const [customTo, setCustomTo] = useState<string | null>(null);

  function seedCustomFromPeriod(): { from: string; to: string } {
    // El `to` se capa a HOY: sembrar hasta fin de año/mes en el período en
    // curso metía fechas futuras (sin datos) en el rango por defecto.
    const today = todayDayStr();
    const cap = (to: string): string => (to > today ? today : to);
    const [y] = anchorMonth.split('-').map(Number);
    const yy = y ?? new Date().getFullYear();
    if (range === 'year') {
      return { from: `${yy}-01-01`, to: cap(`${yy}-12-31`) };
    }
    // PHASE-47 — la semilla es EL PERÍODO QUE SE ESTABA VIENDO, y para quien
    // declaró un día de corte eso es su mes, no el natural. Sembrar con el mes
    // de calendario hacía que pulsar «Personalizado» desplazara el rango sin
    // que el usuario tocara nada: con D=14 viendo 14-jul→13-ago, los pickers
    // salían con 1-jul→31-jul.
    const bounds = boundsForUserPeriod('month', anchorMonth, { cycleStartDay });
    return {
      from: bounds.dateFrom.slice(0, 10),
      to: cap(bounds.dateTo.slice(0, 10)),
    };
  }

  function handleRangeChange(next: PeriodKey): void {
    // Al entrar en el preset, el ancla tiene que ser la del ciclo EN CURSO, no
    // la del mes natural: con D=14, el 5 de agosto el usuario sigue dentro del
    // ciclo que abrió el 14 de julio. Anclar en `2026-08` pintaría el ciclo
    // 14-ago → 13-sep, que todavía no ha empezado — todos los KPIs a cero bajo
    // un titular que dice ser el período actual. Pasa los días 1..13 de cada
    // mes, o sea ~13 de cada 31.
    if (next === 'custom' && !(customFrom && customTo)) {
      const seed = seedCustomFromPeriod();
      setCustomFrom(seed.from);
      setCustomTo(seed.to);
    }
    setRange(next);
  }

  function handleCustomRangeChange(from: string, to: string): void {
    if (from) setCustomFrom(from);
    if (to) setCustomTo(to);
  }
  // PHASE-30.6 — el selector global de divisa del header pasa por aquí
  // como `target_currency` a los tres endpoints de deuda. Sin `convertAll`
  // (modo legacy del dashboard) volvemos al comportamiento native:
  // moneda de referencia de la primera cuenta del usuario.
  // C3a — el día del ciclo del usuario; sin ajuste el navegador no ofrece el chip.
  const { data: me } = useMe();
  const cycleStartDay = me?.cycle_start_day ?? undefined;
  /*
   * PHASE-47 — el reanclaje al período EN CURSO vive en un EFECTO, no en el
   * manejador, y la diferencia no es de estilo.
   *
   * Aquí estaba dentro de `handleRangeChange`, que el navegador invoca como
   * `onRangeChange`… y acto seguido llama a `onAnchorChange(clampAnchor(…,
   * anchor, …))` con el `anchor` del render ANTERIOR. Dos `setState` planas en
   * el mismo evento: ganaba la segunda, así que el reanclaje era código muerto
   * y del día 1 al D−1 la pantalla abría un período que aún no había empezado
   * —todos los KPIs a cero bajo un titular que dice ser el actual—. Lo destapó
   * una revisión adversarial; el gate lo daba por bueno porque el fichero
   * MENCIONA `cycleAnchorContaining`.
   *
   * En un efecto corre después de las dos escrituras y gana. Sólo actúa al
   * ENTRAR en el período mensual y una vez: si el usuario navega con las
   * flechas, mandan sus flechas.
   */
  const rangoPrevio = useRef(range);
  useEffect(() => {
    const acababaDeEntrar = rangoPrevio.current !== range;
    rangoPrevio.current = range;
    if (!acababaDeEntrar) return;
    const dia = cycleDayForPeriod(range, cycleStartDay);
    if (dia === null) return;
    const enCurso = cycleAnchorContaining(todayDayStr(), dia);
    if (enCurso !== anchorMonth) setAnchorMonth(enCurso);
  }, [range, cycleStartDay, anchorMonth]);

  const storeCurrency = useCurrencyStore((s) => s.currency);
  const convertAll = useCurrencyStore((s) => s.convertAll);
  const targetCurrency = convertAll ? storeCurrency : undefined;

  /*
   * C3a — El ciclo viaja a la API como rango libre día-exacto, que es la
   * fontanería que PHASE-42 dejó puesta y que el backend de deuda ya valida.
   * NO existe `range=cycle` en ese contrato: mandarlo daría 422.
   */
  // PHASE-47 — el disparador es el PERFIL: «Mes» corta por el ciclo cuando el
  // usuario declaró un día. La API de deuda sólo entiende `month|year|custom`,
  // así que un mes con corte propio viaja como rango libre día-exacto.
  const cycleDay = cycleDayForPeriod(range, cycleStartDay);
  const cycleDays = cycleDay !== null ? cycleDaysForAnchor(cycleDay, anchorMonth) : null;
  const apiRange: DebtTimeRange = cycleDay !== null ? 'custom' : range;
  const effectiveFrom = cycleDays ? cycleDays.fromDay : customFrom;
  const effectiveTo = cycleDays ? cycleDays.toDay : customTo;

  const summaryQuery = useDebtCategorySummary(apiRange, {
    anchor: `${anchorMonth}-01`,
    ...(effectiveFrom ? { dateFrom: effectiveFrom } : {}),
    ...(effectiveTo ? { dateTo: effectiveTo } : {}),
    ...(targetCurrency ? { targetCurrency } : {}),
  });
  const healthQuery = useDebtHealth(
    targetCurrency ? { targetCurrency } : {},
  );
  // AUDIT-2026-06 — la DebtList y el total "Con plazos" deben respetar
  // el selector de divisa igual que el resto de la página; antes se
  // quedaban en divisa nativa mientras KPIs/charts se convertían.
  const balancesQuery = useAccountBalances(
    targetCurrency ? { targetCurrency } : {},
  );
  const historyQuery = useDebtHistory({
    monthsBack: 12,
    monthsAhead: 12,
    ...(targetCurrency ? { targetCurrency } : {}),
  });

  // PHASE-43.5 — bounds ISO del período para la lista de movimientos de deuda
  // (misma convención mes/año/custom que Análisis/Dashboard).
  const { dateFrom: movementsFrom, dateTo: movementsTo } = useMemo(
    () =>
      boundsForUserPeriod(range, anchorMonth, { cycleStartDay, customFrom, customTo }),
    [range, anchorMonth, customFrom, customTo, cycleStartDay],
  );

  const liabilities = useMemo(
    () =>
      (balancesQuery.data?.items ?? []).filter(
        (item) => item.nature === 'liability',
      ),
    [balancesQuery.data],
  );

  const summary = summaryQuery.data;
  const health = healthQuery.data;

  const referenceCurrency =
    summary?.reference_currency ??
    health?.reference_currency ??
    historyQuery.data?.reference_currency ??
    balancesQuery.data?.reference_currency ??
    'EUR';

  // PHASE-30.8 — Numerador (pagos a deuda) y denominador (ingreso) del
  // período, ambos del category-summary, para que el gauge y las cifras
  // sean coherentes con el período elegido. El numerador ampliado se
  // deriva del ratio ampliado (el backend no expone su absoluto).
  const monthlyIncome = summary?.monthly_income_avg ?? '0';
  const monthlyDebtPayment = summary?.monthly_debt_payment_avg ?? '0';
  const monthlyDebtPaymentExtended =
    summary && summary.effort_ratio_extended !== null
      ? (
          summary.effort_ratio_extended * Number(monthlyIncome)
        ).toFixed(2)
      : monthlyDebtPayment;

  // PHASE-43.x — Composición de la DEUDA VIVA por tipo AL CIERRE del período
  // (period-scoped): sale de `category-summary.outstanding_by_type`, no de
  // debt-health (que era "ahora" fijo). A año/hoy coincide con debt-health; al
  // navegar a un mes pasado muestra la deuda de entonces. Respeta el navegador.
  const debtComposition = summary?.outstanding_by_type ?? [];

  return (
    <div style={{ maxWidth: layout.pageWide, margin: '0 auto', padding: spacing.lg }}>
      <PageHeader />

      <DebtKpiStrip
        health={health}
        outstandingAtEnd={summary?.outstanding_at_end}
        interestsPaidPeriod={summary?.interests_and_fees}
        currency={referenceCurrency}
        isLoading={healthQuery.isLoading || summaryQuery.isLoading}
      />

      <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.md }}>
        <PeriodNavigator
          range={range}
          onRangeChange={handleRangeChange}
          anchor={anchorMonth}
          onAnchorChange={setAnchorMonth}
          availableFrom={summary?.available_from ?? null}
          availableTo={summary?.available_to ?? null}
          allowCustom
          customFrom={customFrom}
          customTo={customTo}
          onCustomRangeChange={handleCustomRangeChange}
          cycleStartDay={cycleStartDay}
          // El endpoint de deuda NO tiene parámetro `cycle`, así que sus
          // `available_*` son meses naturales y hay que traducirlos. Sin esto,
          // el ciclo que contiene el primer movimiento queda inalcanzable.
          boundsAlreadyInCycles={false}
        />
        {summaryQuery.isError ? (
          <ErrorState
            description="No se pudieron cargar tus métricas de deuda. Las cifras de abajo pueden estar incompletas."
            onRetry={() => void summaryQuery.refetch()}
            retrying={summaryQuery.isFetching}
            compact
          />
        ) : null}
        <EffortRatioSection
          strictRatio={summary?.effort_ratio_strict ?? null}
          strictStatus={summary?.effort_ratio_strict_status ?? 'unknown'}
          extendedRatio={summary?.effort_ratio_extended ?? null}
          extendedStatus={summary?.effort_ratio_extended_status ?? 'unknown'}
          monthlyIncome={monthlyIncome}
          monthlyDebtPayment={monthlyDebtPayment}
          monthlyDebtPaymentExtended={monthlyDebtPaymentExtended}
          currency={referenceCurrency}
          isLoading={summaryQuery.isLoading}
        />

        <PaymentsSummaryCard
          title={`Pagos a deuda — ${
            range === 'custom'
              ? formatRangeLabel(customFrom, customTo)
              : periodLabel(range, anchorMonth)
          }`}
          totalPayments={summary?.total_payments ?? '0'}
          interestsAndFees={summary?.interests_and_fees ?? '0'}
          capitalAmortized={summary?.capital_amortized ?? '0'}
          currency={referenceCurrency}
          isLoading={summaryQuery.isLoading}
        />

        <DebtMovementsCard
          dateFrom={movementsFrom}
          dateTo={movementsTo}
          currency={referenceCurrency}
        />

        {/* Ratio 1:1.6 (donut compacto, gráfica ancha) preservado en desktop;
            colapsa a 1 columna por debajo de 900px vía media query (los estilos
            inline no admiten @media). */}
        <style>{`@media (max-width: 900px){.debt-layer1-grid{grid-template-columns:1fr !important}}`}</style>
        <div
          className="debt-layer1-grid"
          style={{
            display: 'grid',
            gridTemplateColumns: 'minmax(280px, 1fr) minmax(360px, 1.6fr)',
            gap: spacing.md,
          }}
        >
          <DebtCompositionDonut
            items={debtComposition}
            total={summary?.outstanding_at_end ?? '0'}
            currency={referenceCurrency}
            isLoading={summaryQuery.isLoading}
          />
          {/*
          * PHASE-47 — la condición mira `apiRange`, no el período de la UI. La
          * serie DIARIA sólo la calcula el backend con `range=month`, y un mes
          * con corte propio viaja como `custom`: preguntando por el período de
          * pantalla, un usuario con ciclo vería el chart diario vacío en vez de
          * la serie mensual con su aviso. Lo cazó un test, no una lectura.
          */}
        {apiRange === 'month' ? (
            <DebtDailyEvolution
              items={summary?.daily_series ?? []}
              currency={referenceCurrency}
              isLoading={summaryQuery.isLoading}
              // Esta rama sólo existe con `apiRange === 'month'`, que implica
              // mes de calendario; `periodLabel` no acepta `custom` y el
              // compilador no puede deducir la implicación.
              monthLabel={periodLabel('month', anchorMonth)}
            />
          ) : (
            <DebtMonthlyEvolution
              items={summary?.monthly_series ?? []}
              currency={referenceCurrency}
              isLoading={summaryQuery.isLoading}
            />
          )}
        </div>

        <RecurringQuotasList
          items={summary?.recurring_quotas ?? []}
          currency={referenceCurrency}
          isLoading={summaryQuery.isLoading}
        />

        <Layer2Section
          hasLiabilities={liabilities.length > 0}
          hasRecurringQuotas={(summary?.recurring_quotas.length ?? 0) > 0}
        >
          {historyQuery.data && historyQuery.data.items.length > 0 ? (
            <DebtTrendChart
              data={historyQuery.data.items}
              currency={referenceCurrency}
              isLoading={historyQuery.isLoading}
            />
          ) : null}
          <DebtList
            liabilities={liabilities}
            loading={balancesQuery.isLoading}
          />
        </Layer2Section>
      </div>
    </div>
  );
}

/**
 * PHASE-37 — Franja de KPIs de deuda desde debt-health (fuente única
 * dirigida por el cuadro). Muestra las cifras que antes faltaban o salían a
 * cero: deuda viva total y los intereses (pagados en el año, contractual
 * total y restante), todos derivados del cuadro de amortización.
 */
function DebtKpiStrip({
  health,
  outstandingAtEnd,
  interestsPaidPeriod,
  currency,
  isLoading,
}: {
  health: DebtHealthKpis | undefined;
  /** PHASE-43.x — deuda viva al cierre del período (period-scoped). */
  outstandingAtEnd: string | undefined;
  /** PHASE-43.x — intereses pagados DURANTE el período (period-scoped). */
  interestsPaidPeriod: string | undefined;
  currency: string;
  isLoading: boolean;
}) {
  const tiles: { label: string; value: string; hint: string; info: string }[] = [
    {
      label: 'Deuda viva total',
      value: outstandingAtEnd != null ? formatAmount(outstandingAtEnd, currency) : '—',
      hint: 'Al cierre del período',
      info: 'Lo que debes en total al final del período, según el capital pendiente del cuadro de amortización de cada préstamo, hipoteca o tarjeta financiada.',
    },
    {
      label: 'Intereses pagados',
      value: interestsPaidPeriod != null ? formatAmount(interestsPaidPeriod, currency) : '—',
      hint: 'Durante el período',
      info: 'Intereses que has pagado dentro del período. Van incluidos en las cuotas (el banco no los cobra como un movimiento aparte), por eso salen del cuadro de amortización.',
    },
    {
      label: 'Interés contractual total',
      value: health ? formatAmount(health.interest_scheduled_total, currency) : '—',
      hint: 'Coste total del crédito',
      info: 'Todos los intereses que pagarás a lo largo de la vida completa de tus créditos, según sus cuadros de amortización. Es el sobrecoste total de financiarte.',
    },
    {
      label: 'Interés restante',
      value: health ? formatAmount(health.interest_remaining, currency) : '—',
      hint: 'Por pagar',
      info: 'Intereses que aún te quedan por pagar: la suma de la parte de interés de las cuotas pendientes de todos tus créditos.',
    },
  ];
  return (
    <div
      role="group"
      aria-label="Indicadores de deuda"
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 160px), 1fr))',
        backgroundColor: colors.surface,
        border: `1px solid ${colors.border}`,
        borderRadius: radius.md,
        overflow: 'hidden',
        marginBottom: spacing.md,
        opacity: isLoading ? 0.6 : 1,
      }}
    >
      {tiles.map((t, i) => (
        <div
          key={t.label}
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 4,
            padding: `${spacing.sm}px ${spacing.md}px`,
            borderLeft: i > 0 ? `1px solid ${colors.border}` : 'none',
            minWidth: 0,
          }}
        >
          <span
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              fontSize: 10,
              fontWeight: fontWeight.semibold,
              letterSpacing: '0.05em',
              textTransform: 'uppercase',
              color: colors.textMuted,
            }}
          >
            <span
              style={{
                minWidth: 0,
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
            >
              {t.label}
            </span>
            <InfoTooltip text={t.info} label={`Qué es «${t.label}»`} />
          </span>
          <span
            style={{
              fontSize: fontSize.xl,
              fontWeight: fontWeight.bold,
              color: colors.text,
              letterSpacing: '-0.01em',
              fontVariantNumeric: 'tabular-nums',
              lineHeight: 1.1,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {t.value}
          </span>
          <span style={{ fontSize: 10, color: colors.textSubtle }}>{t.hint}</span>
        </div>
      ))}
    </div>
  );
}

function PageHeader() {
  return (
    <header
      style={{
        display: 'flex',
        alignItems: 'flex-end',
        justifyContent: 'space-between',
        gap: spacing.md,
        flexWrap: 'wrap',
        marginBottom: spacing.xl,
      }}
    >
      <div>
        <span
          style={{
            fontSize: 11,
            fontWeight: fontWeight.semibold,
            color: colors.primary,
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
            display: 'block',
            marginBottom: spacing.xs,
          }}
        >
          DEUDA
        </span>
        <h1
          style={{
            margin: 0,
            fontSize: fontSize.xxl,
            fontWeight: fontWeight.bold,
            color: colors.text,
            letterSpacing: '-0.02em',
            lineHeight: 1.1,
          }}
        >
          Deuda
        </h1>
        <p
          style={{
            margin: `${spacing.xs}px 0 0 0`,
            color: colors.textMuted,
            fontSize: fontSize.sm,
            maxWidth: layout.prose,
            lineHeight: 1.5,
          }}
        >
          Tu salud financiera de un vistazo: cuánto destinas a deuda
          frente a tus ingresos, qué proporción es interés puro y
          cómo evoluciona mes a mes.
        </p>
      </div>
      <Link
        href="/settings/accounts"
        style={{
          display: 'inline-block',
          padding: `${spacing.sm}px ${spacing.md}px`,
          borderRadius: radius.md,
          backgroundColor: colors.primary,
          color: colors.onPrimary,
          fontSize: fontSize.sm,
          fontWeight: fontWeight.semibold,
          textDecoration: 'none',
          border: `1px solid ${colors.primary}`,
        }}
      >
        Añadir deuda
      </Link>
    </header>
  );
}

function Layer2Section({
  hasLiabilities,
  hasRecurringQuotas,
  children,
}: {
  hasLiabilities: boolean;
  hasRecurringQuotas: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(hasLiabilities);
  // AUDIT-2026-07: `hasLiabilities` suele ser false en el primer render (los
  // balances aún cargan), así que el estado inicial no auto-expandía nunca.
  // Nos auto-abrimos cuando pasa a true, salvo que el usuario ya lo haya
  // tocado (respeta un cierre manual posterior).
  const userToggled = useRef(false);
  useEffect(() => {
    if (!userToggled.current && hasLiabilities) setOpen(true);
  }, [hasLiabilities]);

  return (
    <section
      style={{
        backgroundColor: colors.surface,
        border: `1px solid ${colors.border}`,
        borderRadius: radius.md,
      }}
    >
      <button
        type="button"
        onClick={() => {
          userToggled.current = true;
          setOpen((o) => !o);
        }}
        style={{
          width: '100%',
          background: 'transparent',
          border: 'none',
          padding: `${spacing.md}px ${spacing.lg}px`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          cursor: 'pointer',
          textAlign: 'left',
        }}
        aria-expanded={open}
      >
        <span>
          <span
            style={{
              fontSize: fontSize.md,
              fontWeight: fontWeight.semibold,
              color: colors.text,
              letterSpacing: '-0.01em',
            }}
          >
            Detalle por contrato
          </span>
          <span
            style={{
              display: 'block',
              fontSize: fontSize.xs,
              color: colors.textMuted,
              marginTop: 2,
            }}
          >
            {hasLiabilities
              ? 'Tus pasivos declarados con sus cuotas y cuadros de amortización.'
              : hasRecurringQuotas
                ? 'Cuotas detectadas pero sin contrato vinculado — añade uno para que cuenten en tu patrimonio.'
                : 'Vacío. Añade un préstamo / hipoteca / tarjeta cuando tengas un contrato real.'}
          </span>
        </span>
        <span
          aria-hidden
          style={{
            fontSize: fontSize.lg,
            color: colors.textMuted,
            transform: open ? 'rotate(180deg)' : 'rotate(0deg)',
            transition: 'transform 120ms ease',
          }}
        >
          ▾
        </span>
      </button>

      {open ? (
        <div
          style={{
            padding: `0 ${spacing.lg}px ${spacing.lg}px`,
            display: 'flex',
            flexDirection: 'column',
            gap: spacing.md,
          }}
        >
          {children}
        </div>
      ) : null}
    </section>
  );
}
