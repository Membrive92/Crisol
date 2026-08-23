import { useEffect, useRef, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Stack, useRouter } from 'expo-router';

import {
  cycleAnchorContaining,
  cycleDaysForAnchor,
  isValidCycleStartDay,
  todayDayStr,
  periodLabel,
  useAccountBalances,
  useAccounts,
  useDebtCategorySummary,
  useDebtHealth,
  useDebtHistory,
  useMe,
  boundsForUserPeriod,
  cycleDayForPeriod,
} from '@crisol/services';
import { useCurrencyStore } from '@crisol/store';
import type { Account, DebtTimeRange, PeriodKey } from '@crisol/types';
import {
  colors,
  fontSize,
  fontWeight,
  radius,
  spacing,
} from '@crisol/ui';

import { DebtPaymentWizard } from '../../../components/accounts/debt-payment-wizard';
import { DebtCompositionDonut } from '../../../components/debt/debt-composition-donut';
import { DebtList } from '../../../components/debt/debt-list';
import { DebtDailyEvolution } from '../../../components/debt/debt-daily-evolution';
import { DebtMonthlyEvolution } from '../../../components/debt/debt-monthly-evolution';
import { DebtTrendChart } from '../../../components/debt/debt-trend-chart';
import { EffortRatioSection } from '../../../components/debt/effort-ratio-section';
import { PaymentsSummaryCard } from '../../../components/debt/payments-summary-card';
import { PeriodNavigator } from '../../../components/debt/period-navigator';
import { RecurringQuotasList } from '../../../components/debt/recurring-quotas-list';
import { ErrorState } from '../../../components/ui/error-state';

/**
 * Pantalla `/debt` — paridad mobile de PHASE-30.3 (PHASE-30.5).
 *
 * Mismo modelo en dos capas:
 * - Capa 1 (arriba): KPIs derivados del flujo de categorías.
 * - Capa 2 (debajo, colapsable): pasivos declarados + cuadro de
 *   amortización vía link al detalle del préstamo.
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

export default function DebtScreen() {
  const router = useRouter();
  // C3a — El estado es `PeriodKey` (vocabulario de la UI, con `cycle`). La API
  // de deuda sólo entiende `month|year|custom`, así que el ciclo se le manda
  // como rango libre con sus dos fechas: `apiRange`/`cycleDays`, más abajo.
  const [range, setRange] = useState<PeriodKey>('year');
  // PHASE-30.8 — Mes ancla `YYYY-MM`; por defecto el mes en curso →
  // período actual (comportamiento previo). El `PeriodNavigator` lo
  // mueve, limitado a los meses con datos.
  const [anchorMonth, setAnchorMonth] = useState(() => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
  });
  // PHASE-41 — rango libre (`range='custom'`): day-strings `YYYY-MM-DD`,
  // sembrados desde el período actual al conmutar a "Rango".
  const [customFrom, setCustomFrom] = useState<string | null>(null);
  const [customTo, setCustomTo] = useState<string | null>(null);
  const [layer2Open, setLayer2Open] = useState(false);
  const [payingDebt, setPayingDebt] = useState<Account | null>(null);

  function seedCustomFromPeriod(): { from: string; to: string } {
    const [y] = anchorMonth.split('-').map(Number);
    const yy = y ?? new Date().getFullYear();
    if (range === 'year') {
      return { from: `${yy}-01-01`, to: `${yy}-12-31` };
    }
    // PHASE-47 — la semilla es EL PERÍODO QUE SE ESTABA VIENDO, y para quien
    // declaró un día de corte eso es su mes, no el natural.
    const bounds = boundsForUserPeriod('month', anchorMonth, { cycleStartDay });
    return {
      from: bounds.dateFrom.slice(0, 10),
      to: bounds.dateTo.slice(0, 10),
    };
  }

  function handleRangeChange(next: PeriodKey): void {
    // Al entrar en el preset, el ancla es la del ciclo EN CURSO, no la del mes
    // natural: con D=14, el 5 de agosto el usuario sigue dentro del ciclo que
    // abrió el 14 de julio. Anclar en el mes pintaría 14-ago → 13-sep, que aún
    // no ha empezado: todos los KPIs a cero bajo un titular que dice ser el
    // período actual. Pasa los días 1..13 de cada mes. La pantalla de Análisis
    // de esta misma app ya lo derivaba así; sin esto, las dos enseñaban ciclos
    // distintos el mismo día.
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

  // PHASE-30.6 — el selector global de divisa pasa por aquí como
  // `target_currency` a los tres endpoints (mismo wiring que web).
  // C3a — el día del ciclo del usuario; sin ajuste el navegador no ofrece el
  // chip. Guarda por VERDAD: con un backend anterior a la columna el campo
  // llega AUSENTE (lección PHASE-47.E).
  const { data: me } = useMe();
  const savedCycleDay = me?.cycle_start_day;
  const cycleStartDay = isValidCycleStartDay(savedCycleDay) ? savedCycleDay : undefined;

  /*
   * PHASE-47 — el reanclaje al período EN CURSO vive en un EFECTO, no en el
   * manejador, y la diferencia no es de estilo.
   *
   * Estaba dentro de `handleRangeChange`, que el navegador invoca como
   * `onRangeChange`… y acto seguido llama a `onAnchorChange(clampAnchor(…,
   * anchor, …))` con el `anchor` del render ANTERIOR. Dos `setState` planas en
   * el mismo evento: ganaba la segunda, así que el reanclaje era código muerto
   * y del día 1 al D−1 la pantalla abría un período que aún no había empezado.
   * En un efecto corre después de las dos y gana.
   *
   * Sólo actúa al ENTRAR en el período mensual: si el usuario navega con las
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
  // PHASE-47 — el disparador es el PERFIL, no un preset elegido: «Mes» corta
  // por el ciclo cuando el usuario declaró un día de inicio.
  const cycleDay = cycleDayForPeriod(range, cycleStartDay);
  const monthIsCycle = cycleDay !== null;
  const cycleDays = cycleDay !== null ? cycleDaysForAnchor(cycleDay, anchorMonth) : null;
  // La API de deuda sólo entiende `month|year|custom`; un mes con corte propio
  // viaja como rango libre día-exacto (la fontanería de PHASE-42).
  const apiRange: DebtTimeRange = monthIsCycle ? 'custom' : range;
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
  // AUDIT-2026-07 (M-05): pasar `targetCurrency` como el resto de la pantalla.
  // Sin él, la DebtList quedaba en divisa nativa mientras esfuerzo/pagos/donut
  // ya estaban convertidos → dos divisas distintas en la misma pantalla.
  const balancesQuery = useAccountBalances(
    targetCurrency ? { targetCurrency } : {},
  );
  const accountsQuery = useAccounts({ includeArchived: false });
  const historyQuery = useDebtHistory({
    monthsBack: 12,
    monthsAhead: 12,
    ...(targetCurrency ? { targetCurrency } : {}),
  });

  const summary = summaryQuery.data;
  const health = healthQuery.data;
  const balances = balancesQuery.data?.items ?? [];
  const accounts = accountsQuery.data ?? [];
  const liabilities = balances.filter((b) => b.nature === 'liability');

  const referenceCurrency =
    summary?.reference_currency ??
    health?.reference_currency ??
    historyQuery.data?.reference_currency ??
    balancesQuery.data?.reference_currency ??
    'EUR';

  // PHASE-30.8 — numerador (pagos) y denominador (ingreso) del período,
  // ambos del category-summary, coherentes con el período elegido.
  const monthlyIncome = summary?.monthly_income_avg ?? '0';
  const monthlyDebtPayment = summary?.monthly_debt_payment_avg ?? '0';
  const monthlyDebtPaymentExtended =
    summary && summary.effort_ratio_extended !== null
      ? (summary.effort_ratio_extended * Number(monthlyIncome)).toFixed(2)
      : monthlyDebtPayment;

  // Capa 2 se auto-abre cuando hay liabilities reales — coherente con
  // el comportamiento de la web.
  const hasLiabilities = liabilities.length > 0;
  const expanded = layer2Open || hasLiabilities;

  return (
    <>
      <Stack.Screen options={{ title: 'Deuda' }} />
      <ScrollView style={styles.container} contentContainerStyle={styles.content}>
        <View style={styles.header}>
          <View style={{ flex: 1 }}>
            <Text style={styles.eyebrow}>DEUDA</Text>
            <Text style={styles.title}>Deuda</Text>
            <Text style={styles.subtitle}>
              Cuánto destinas a deuda vs ingresos, qué es interés puro
              y cómo evoluciona mes a mes.
            </Text>
          </View>
          <Pressable
            style={({ pressed }) => [styles.addButton, pressed && { opacity: 0.85 }]}
            onPress={() => router.push('/personal-finance/accounts')}
          >
            <Text style={styles.addButtonText}>Añadir deuda</Text>
          </Pressable>
        </View>

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
          // El endpoint de deuda no tiene `cycle`: sus bounds son meses
          // naturales y hay que traducirlos, o el ciclo que contiene el primer
          // movimiento queda inalcanzable.
          boundsAlreadyInCycles={false}
        />

        {summaryQuery.isError ? (
          <ErrorState
            description="No se pudieron cargar tus métricas de deuda. Las cifras de abajo pueden estar incompletas."
            onRetry={() => void summaryQuery.refetch()}
            retrying={summaryQuery.isFetching}
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

        <DebtCompositionDonut
          items={summary?.by_type ?? []}
          total={summary?.total_payments ?? '0'}
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
          <>
            <DebtMonthlyEvolution
              items={summary?.monthly_series ?? []}
              currency={referenceCurrency}
              isLoading={summaryQuery.isLoading}
            />
            {/* PHASE-47 — aquí vivía un aviso de «esta tarjeta cuenta el mes
                de siempre»: la serie mensual cortaba por calendario mientras
                el resto de la pantalla cortaba por el mes del usuario, y una
                diferencia que nadie nombra se lee como un fallo. Ya no hace
                falta: la serie corta por el mismo período que todo lo demás. */}
          </>
        )}

        <RecurringQuotasList
          items={summary?.recurring_quotas ?? []}
          currency={referenceCurrency}
          isLoading={summaryQuery.isLoading}
        />

        <View style={styles.layer2Wrap}>
          <Pressable
            onPress={() => setLayer2Open((o) => !o)}
            style={styles.layer2Header}
            accessibilityRole="button"
            accessibilityState={{ expanded }}
          >
            <View style={{ flex: 1 }}>
              <Text style={styles.layer2Title}>Detalle por contrato</Text>
              <Text style={styles.layer2Subtitle}>
                {hasLiabilities
                  ? 'Tus pasivos declarados con sus cuotas y cuadros.'
                  : 'Sin contratos declarados. Añade un préstamo / hipoteca / tarjeta cuando tengas uno.'}
              </Text>
            </View>
            <Text style={[styles.layer2Caret, expanded && styles.layer2CaretOpen]}>▾</Text>
          </Pressable>
          {expanded ? (
            <View style={styles.layer2Body}>
              {historyQuery.data && historyQuery.data.items.length > 0 ? (
                <DebtTrendChart
                  data={historyQuery.data.items}
                  currency={referenceCurrency}
                  isLoading={historyQuery.isLoading}
                />
              ) : null}
              <DebtList
                balances={balances}
                accounts={accounts}
                isLoading={balancesQuery.isLoading || accountsQuery.isLoading}
                onPayDebt={setPayingDebt}
              />
            </View>
          ) : null}
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
  naturalNotice: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
    lineHeight: 18,
    marginTop: -spacing.xs,
  },
  layer2Wrap: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    overflow: 'hidden',
  },
  layer2Header: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: spacing.md,
    gap: spacing.sm,
  },
  layer2Title: {
    fontSize: fontSize.md,
    fontWeight: fontWeight.semibold,
    color: colors.text,
  },
  layer2Subtitle: {
    marginTop: 2,
    fontSize: fontSize.xs,
    color: colors.textMuted,
  },
  layer2Caret: {
    fontSize: fontSize.lg,
    color: colors.textMuted,
    transform: [{ rotate: '0deg' }],
  },
  layer2CaretOpen: {
    transform: [{ rotate: '180deg' }],
  },
  layer2Body: {
    paddingHorizontal: spacing.md,
    paddingBottom: spacing.md,
    gap: spacing.md,
  },
});
