'use client';

import { useEffect, useMemo, useRef, useState } from 'react';

import {
  // C0 — `calendarPeriodFor` reemplaza al `period === 'custom' ? 'year' : period`
  // que había inline: `PeriodKey` ya incluye `cycle` y ese ternario dejaba de
  // tipar. Ver su docstring: es un FALLBACK de calendario, no el ciclo.
  useAccountBalances,
  useDashboardSummary,
  useDebtDashboardSummary,
  useModuleSummary,
  useMonthOutlook,
  usePositionAsOf,
  useMe,
  usePositionHistory,
  boundsForUserPeriod,
  userMonthIsCycle,
  userMonthAnchorContaining,
} from '@crisol/services';
import { useCurrencyStore } from '@crisol/store';
import { colors, fontSize, fontWeight, formatAmount, layout, spacing } from '@crisol/ui';

import { AccountsSection } from '@/components/analysis/accounts-section';
import { KpiStrip, KpiTile, MiniSparkline } from '@/components/analysis/kpi-strip';
import { MonthOutlookCard } from '@/components/analysis/month-outlook-card';
import { NetworthEvolutionCard } from '@/components/analysis/networth-evolution-card';
import {
  type PeriodKey,
} from '@/components/analysis/stitch-period-toggle';
import { ModuleCard } from '@/components/dashboard/module-card';
import { PeriodNavigator } from '@/components/debt/period-navigator';
import { todayDayStr } from '@/components/ui/date-picker';

function fmtSignedAmount(value: string | number, currency: string): string {
  const n = Number(value);
  return `${n >= 0 ? '+' : ''}${formatAmount(String(n.toFixed(2)), currency)}`;
}

/**
 * PHASE-43.4 (ADR-0006) — Dashboard = STOCKS. Responde *"¿cuánto valgo?"*:
 * patrimonio consolidado (la única métrica que cruza módulos), resiliencia y
 * una tarjeta-resumen por módulo (`veredicto + número + link`). Los flujos
 * (gastos, ahorro, evolución mensual) viven en Análisis.
 */
export default function DashboardPage() {
  const currency = useCurrencyStore((s) => s.currency);
  const convertAll = useCurrencyStore((s) => s.convertAll);
  const includeDebt = useCurrencyStore((s) => s.includeDebtInNetWorth);
  const targetCurrency = convertAll ? currency : undefined;

  // C3a — el día en que empieza el mes del usuario. Sin ajuste, `undefined` y
  // ninguna de las ramas de ciclo se activa.
  const { data: me } = useMe();
  const cycleStartDay = me?.cycle_start_day ?? undefined;

  const [period, setPeriod] = useState<PeriodKey>('year');
  const [anchorMonth, setAnchorMonth] = useState(() => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
  });
  const [customFrom, setCustomFrom] = useState<string | null>(null);
  /*
   * PHASE-47 — reanclar al período EN CURSO cuando llega el perfil.
   *
   * El ancla se siembra en el primer render con el mes de CALENDARIO, porque
   * `useState` es síncrono y `cycleStartDay` llega de `useMe()`, que no lo es.
   * Para quien tiene corte a mitad de mes eso apunta a un período que aún no
   * ha empezado: con D=12, del 1 al 11 el mes de calendario `2026-08` es el
   * que abrirá el 12 de agosto, así que la pantalla enseñaría todos los KPIs
   * a cero bajo un titular que dice ser el período actual. Un tercio de los
   * días del mes.
   *
   * Antes esto no pasaba porque el ciclo exigía pulsar un chip, y el manejador
   * de ese chip reanclaba. Al pasar a gobernarlo el perfil, el reanclaje se
   * fue con el manejador.
   *
   * Sólo corrige el ancla SEMBRADA (la del mes de calendario actual): si el
   * usuario ya ha navegado, mandan sus flechas.
   */
  const semilla = useRef(anchorMonth);
  useEffect(() => {
    if (!userMonthIsCycle(cycleStartDay)) return;
    if (anchorMonth !== semilla.current) return;
    const enCurso = userMonthAnchorContaining(todayDayStr(), cycleStartDay);
    if (enCurso !== anchorMonth) setAnchorMonth(enCurso);
  }, [cycleStartDay, anchorMonth]);

  const [customTo, setCustomTo] = useState<string | null>(null);
  function handleRangeChange(next: PeriodKey): void {
    setPeriod(next);
    if (next === 'custom' && !(customFrom && customTo)) {
      // PHASE-47 — la semilla es EL PERÍODO QUE SE ESTABA VIENDO, y para quien
      // declaró un día de corte eso es su mes, no el natural. Sembrar con el
      // mes de calendario hacía que pulsar «Personalizado» desplazara el rango
      // sin tocar nada — y lo cazó el gate de cableado, no una revisión.
      const seed = boundsForUserPeriod(period === 'custom' ? 'month' : period, anchorMonth, {
        cycleStartDay,
      });
      const today = todayDayStr();
      const to = seed.dateTo.slice(0, 10);
      setCustomFrom(seed.dateFrom.slice(0, 10));
      setCustomTo(to > today ? today : to);
    }
  }

  const { dateFrom, dateTo } = useMemo(
    () =>
      // PHASE-47 — UNA sola declaración de qué bounds tiene el período. Aquí
      // había un ternario de tres ramas, repetido en cinco pantallas, en el que
      // olvidar el orden degradaba al mes NATURAL en silencio (mismo tipo,
      // rango distinto).
      boundsForUserPeriod(period, anchorMonth, { cycleStartDay, customFrom, customTo }),
    [period, anchorMonth, customFrom, customTo, cycleStartDay],
  );

  /*
   * PHASE-47 — el flag que faltaba. Esta pantalla pasaba
   * `boundsAlreadyInCycles` al navegador —afirmando que sus bounds vienen en
   * ciclos— y sin embargo NUNCA pedía `cycle=true`, así que el servidor le
   * devolvía `available_from`/`available_to` en meses naturales y las flechas
   * se acotaban con la unidad equivocada. Convivía con el bug porque el ciclo
   * exigía un clic y casi nadie llegaba aquí con el preset puesto; al pasar a
   * gobernarlo el perfil, sería el caso normal.
   *
   * La guarda no es redundante con la de los bounds: si el usuario vuelve al
   * mes natural desde otro dispositivo y `useMe()` refresca, mandar el flag sin
   * el dato deja la pantalla entera en 422.
   */
  const cycleParam = userMonthIsCycle(cycleStartDay) ? { cycle: true } : {};

  // Metadata para acotar el navegador de período (mes min/max con datos).
  const summaryQuery = useDashboardSummary(
    convertAll
      ? { target_currency: currency, date_from: dateFrom, date_to: dateTo, ...cycleParam }
      : { currency, date_from: dateFrom, date_to: dateTo, ...cycleParam },
  );
  const summary = summaryQuery.data;

  // Patrimonio (stock): foto a fecha de fin del período + Δ durante el rango +
  // serie de 12 meses (tendencia). Salud de deuda y flujo del mes llegan como
  // tarjetas de módulo (contrato de agregación).
  const balancesQuery = useAccountBalances(targetCurrency ? { targetCurrency } : {});
  const positionQuery = usePositionHistory(12, 0);
  const positionAsOfQuery = usePositionAsOf(dateFrom, dateTo);
  const outlookQuery = useMonthOutlook(convertAll ? { target_currency: currency } : { currency });
  const moduleQuery = useModuleSummary(
    convertAll
      ? { target_currency: currency, date_from: dateFrom, date_to: dateTo }
      : { currency, date_from: dateFrom, date_to: dateTo },
  );
  // PHASE-43.x — la deuda viva de la tarjeta es period-scoped (al cierre del
  // rango), coherente con el Patrimonio Neto. Pasamos la PARTE FECHA del rango.
  const debtSummaryQuery = useDebtDashboardSummary({
    ...(targetCurrency ? { targetCurrency } : {}),
    dateFrom: dateFrom.slice(0, 10),
    dateTo: dateTo.slice(0, 10),
  });

  const balances = balancesQuery.data;
  const position = positionQuery.data;
  const positionAsOf = positionAsOfQuery.data;

  const worthKey = includeDebt ? 'net_worth' : 'total_assets';
  const deltaKey = includeDebt ? 'delta_net_worth' : 'delta_assets';
  const netWorth = positionAsOf
    ? positionAsOf[worthKey]
    : balances
      ? balances[worthKey]
      : null;
  const worthSeries = (position?.points ?? []).map((p) => Number(p[worthKey]));
  const deltaPeriod = positionAsOf
    ? Number(positionAsOf[deltaKey])
    : worthSeries.length >= 2
      ? worthSeries[worthSeries.length - 1]! - worthSeries[0]!
      : null;
  const worthStart =
    positionAsOf && netWorth != null && deltaPeriod != null
      ? Number(netWorth) - deltaPeriod
      : worthSeries.length >= 2
        ? worthSeries[0]!
        : null;
  const deltaPeriodPct =
    deltaPeriod != null && worthStart != null && worthStart !== 0
      ? (deltaPeriod / Math.abs(worthStart)) * 100
      : null;
  const worthCurrency = positionAsOf?.reference_currency ?? currency;

  const anyError = summaryQuery.isError || balancesQuery.isError;

  return (
    <div style={{ maxWidth: layout.pageWide, margin: '0 auto', padding: spacing.lg }}>
      <header
        style={{
          display: 'flex',
          alignItems: 'flex-end',
          justifyContent: 'space-between',
          gap: spacing.md,
          flexWrap: 'wrap',
          marginBottom: spacing.lg,
        }}
      >
        <div>
          <h1
            style={{
              margin: 0,
              fontSize: fontSize.xl,
              fontWeight: fontWeight.bold,
              color: colors.text,
              letterSpacing: '-0.01em',
            }}
          >
            Dashboard
          </h1>
          <p style={{ margin: `${spacing.xs}px 0 0 0`, color: colors.textMuted, fontSize: fontSize.sm }}>
            Tu patrimonio y la salud de cada módulo, de un vistazo.
          </p>
        </div>
        <PeriodNavigator
          range={period}
          onRangeChange={handleRangeChange}
          anchor={anchorMonth}
          onAnchorChange={setAnchorMonth}
          availableFrom={summary?.available_from ?? null}
          availableTo={summary?.available_to ?? null}
          allowCustom
          customFrom={customFrom}
          customTo={customTo}
          onCustomRangeChange={(from, to) => {
            setCustomFrom(from);
            setCustomTo(to);
          }}
          cycleStartDay={cycleStartDay}
          // Esta pantalla pide con `cycle=true`, así que sus bounds YA vienen
          // como anclas de ciclo: traducirlos otra vez daría un ciclo vacío.
          boundsAlreadyInCycles
        />
      </header>

      <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.md }}>
        {/* PATRIMONIO — el número que cruza módulos + su evolución. */}
        <KpiStrip>
          <KpiTile
            label="Patrimonio neto"
            info="Todo lo que tienes menos lo que debes (activos − pasivos) a fecha de fin del período. Las deudas con cuadro cuentan su capital pendiente. Excluye brókers/cripto (valor de mercado)."
            value={netWorth != null ? formatAmount(netWorth, worthCurrency) : '—'}
            sparkline={
              worthSeries.length >= 2 ? (
                <MiniSparkline
                  values={worthSeries}
                  up={worthSeries[worthSeries.length - 1]! >= worthSeries[0]!}
                />
              ) : undefined
            }
          />
          <KpiTile
            label="Δ patrimonio"
            info="Cuánto ha cambiado tu patrimonio neto durante el período, comparado con su valor al inicio del rango seleccionado."
            value={deltaPeriod != null ? fmtSignedAmount(deltaPeriod, worthCurrency) : '—'}
            delta={deltaPeriod}
            deltaText={deltaPeriodPct != null ? `${deltaPeriodPct.toFixed(1)} %` : undefined}
            subtitle="vs inicio del rango"
          />
        </KpiStrip>

        <NetworthEvolutionCard
          points={position?.points ?? []}
          currency={position?.reference_currency ?? currency}
          isLoading={positionQuery.isLoading}
          includeDebt={includeDebt}
        />

        {/* MÓDULOS + RESILIENCIA. */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 380px), 1fr))',
            gap: spacing.md,
            alignItems: 'start',
          }}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.sm }}>
            <h2
              style={{
                margin: 0,
                fontSize: fontSize.sm,
                fontWeight: fontWeight.semibold,
                color: colors.textMuted,
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
              }}
            >
              Módulos
            </h2>
            <ModuleCard
              label="Finanzas Domésticas"
              emoji="🏠"
              summary={moduleQuery.data}
              isLoading={moduleQuery.isLoading}
            />
            <ModuleCard
              label="Deuda"
              emoji="💳"
              summary={debtSummaryQuery.data}
              isLoading={debtSummaryQuery.isLoading}
            />
          </div>
          <MonthOutlookCard
            data={outlookQuery.data}
            currency={outlookQuery.data?.reference_currency ?? currency}
            isLoading={outlookQuery.isLoading}
          />
        </div>

        {/* CUENTAS (composición del patrimonio, colapsable). */}
        <AccountsSection />
      </div>

      {anyError ? (
        <p
          style={{
            color: colors.danger,
            marginTop: spacing.md,
            fontSize: fontSize.sm,
            fontWeight: fontWeight.medium,
          }}
        >
          Error cargando alguna sección del dashboard.
        </p>
      ) : null}
    </div>
  );
}
