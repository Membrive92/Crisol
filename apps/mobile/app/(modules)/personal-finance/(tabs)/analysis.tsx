import { useEffect, useMemo, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Link } from 'expo-router';

import {
  authApi,
  isValidCycleStartDay,
  todayDayStr,
  useDashboardByCategory,
  useDashboardByMonth,
  useDashboardSummary,
  useDashboardTopExpenses,
  useExpenseStructure,
  useMe,
  useMonthOutlook,
  useUserCurrencies,
  boundsForUserPeriod,
  userMonthAnchorContaining,
  userMonthIsCycle,
} from '@crisol/services';
import { useAuthStore, useCurrencyStore } from '@crisol/store';
import {
  NATURAL_MONTH_NOTICE,
  colors,
  deferredBreakdownNotice,
  fontSize,
  fontWeight,
  spacing,
} from '@crisol/ui';

import { BalancesCard } from '../../../../components/accounts/balances-card';
import {
  CategoryDonut,
  type DonutKindFilter,
} from '../../../../components/dashboard/category-donut';
import { CurrencyPicker } from '../../../../components/dashboard/currency-picker';
import { DebtHealthCard } from '../../../../components/dashboard/debt-health-card';
import { KpiCards } from '../../../../components/dashboard/kpi-cards';
import { MonthlyChart } from '../../../../components/dashboard/monthly-chart';
import { MonthOutlookCard } from '../../../../components/dashboard/month-outlook-card';
import { NetworthEvolutionCard } from '../../../../components/dashboard/networth-evolution-card';
import {
  PeriodToggle,
  type PeriodKey,
} from '../../../../components/dashboard/period-toggle';
import { SavingsRateCard } from '../../../../components/dashboard/savings-rate-card';
import { SmartInsights } from '../../../../components/dashboard/smart-insights';
import { TopExpensesList } from '../../../../components/dashboard/top-expenses-list';
import { DateInput } from '../../../../components/ui/date-input';
import { ErrorState } from '../../../../components/ui/error-state';
import { FabLink } from '../../../../components/ui/fab';

const TOP_EXPENSES_LIMIT = 5;
const FALLBACK_CURRENCY = 'EUR';

/**
 * Pantalla **Análisis** — paridad con `apps/web/app/(app)/personal-finance/analysis`.
 * Período toggleable Mes/Año, tasa de ahorro, smart insights.
 * El gráfico mensual sigue ligado al año en curso (`useDashboardByMonth`
 * sólo acepta `year`).
 */
export default function AnalysisScreen() {
  const { user, refreshToken, logout: clearAuth } = useAuthStore();
  const queryClient = useQueryClient();
  // PHASE-11.2: la moneda activa vive en `useCurrencyStore`
  // (cross-platform vía AsyncStorage). Antes era `useState` local —
  // se perdía entre sesiones y no se compartía con otras pantallas.
  const currency = useCurrencyStore((s) => s.currency);
  const setCurrency = useCurrencyStore((s) => s.setCurrency);
  // PHASE-14.4: convertAll vive en el mismo store cross-platform
  // (PHASE-11.2). Cuando ON, las queries del dashboard pasan
  // `target_currency` y el backend convierte cada tx con la tasa de
  // su día (mismo flujo que web).
  const convertAll = useCurrencyStore((s) => s.convertAll);
  const setConvertAll = useCurrencyStore((s) => s.setConvertAll);
  const [period, setPeriod] = useState<PeriodKey>('year');
  // PHASE-41 — rango libre (`period='custom'`): day-strings `YYYY-MM-DD`,
  // sembrados desde el período actual al conmutar a "Rango".
  const [customFrom, setCustomFrom] = useState<string | null>(null);
  const [customTo, setCustomTo] = useState<string | null>(null);
  const [donutKind, setDonutKind] = useState<DonutKindFilter>('all');

  function seedCustom(): { from: string; to: string } {
    const now = new Date();
    const y = now.getFullYear();
    if (period === 'year') {
      return { from: `${y}-01-01`, to: `${y}-12-31` };
    }
    // PHASE-47 — la semilla es EL PERÍODO QUE SE ESTABA VIENDO, y para quien
    // declaró un día de corte eso es su mes, no el natural. `userAnchor` ya es
    // el ancla del período en curso del usuario.
    const bounds = boundsForUserPeriod('month', userAnchor, { cycleStartDay });
    return { from: bounds.dateFrom.slice(0, 10), to: bounds.dateTo.slice(0, 10) };
  }

  function handlePeriodChange(next: PeriodKey): void {
    if (next === 'custom' && !(customFrom && customTo)) {
      const seed = seedCustom();
      setCustomFrom(seed.from);
      setCustomTo(seed.to);
    }
    setPeriod(next);
  }

  function handleCustomRangeChange(from: string, to: string): void {
    if (from) setCustomFrom(from);
    if (to) setCustomTo(to);
  }
  const [currencyHydrated, setCurrencyHydrated] = useState(false);

  const currenciesQuery = useUserCurrencies();

  useEffect(() => {
    if (currencyHydrated) return;
    const list = currenciesQuery.data;
    if (!list) return;
    if (list.length === 0) {
      setCurrencyHydrated(true);
      return;
    }
    // Sólo sobrescribir el store si la moneda persistida no está
    // en las del usuario — respeta su selección explícita previa.
    if (!list.includes(currency)) {
      setCurrency(list[0] ?? FALLBACK_CURRENCY);
    }
    setCurrencyHydrated(true);
  }, [currenciesQuery.data, currencyHydrated, currency, setCurrency]);

  // C3a — el día en que empieza el mes del usuario. Guarda por VERDAD
  // (`isValidCycleStartDay`), nunca `!== null`: con un backend anterior a la
  // columna el campo llega AUSENTE y `undefined !== null` es cierto, así que el
  // chip saldría para todo el mundo y al pulsarlo el servidor responde 422
  // (lección PHASE-47.E).
  const { data: me } = useMe();
  const savedCycleDay = me?.cycle_start_day;
  const cycleStartDay = isValidCycleStartDay(savedCycleDay) ? savedCycleDay : undefined;

  // C0 — antes `rangeForPeriod(...)`, que calculaba los BORDES del rango en
  // hora LOCAL. Ahora se usa la MISMA `boundsForAnchor` que web (bordes en UTC,
  // como corta el backend) con ancla explícita; el reloj se lee una sola vez
  // aquí, en el llamante, y la aritmética que recibe el ancla es pura. Cambio
  // de comportamiento deliberado y acotado: en husos ≠ UTC la frontera del
  // rango se mueve hasta 2 h y pasa a coincidir con la de web y la del backend.
  /*
   * C3a — El ancla del CICLO en curso NO es el mes en curso: con D=14, el 5 de
   * agosto el usuario sigue dentro del ciclo que abrió el 14 de julio. Usar
   * `monthAnchor` aquí pintaría un ciclo que todavía no ha empezado (14 ago –
   * 13 sep), o sea un período casi vacío presentado como «el actual».
   *
   * Esta pantalla no guarda ancla —siempre enseña «ahora»—, así que el ancla se
   * deriva del día de hoy con la misma función que usa la previsualización de
   * Ajustes en web. El reloj se lee en LOCAL (`todayDayStr`), que es la
   * pregunta del calendario del usuario; los BOUNDS que salen de ahí siguen
   * siendo UTC, como corta el backend.
   */
  /*
    * PHASE-47 — UN solo ancla, el del mes del usuario. Antes había dos
    * (`monthAnchor` natural y `cycleAnchor`) porque el preset convivía con el
    * mes; ahora `month` ES su mes, así que el ancla se deriva de su día y
    * degenera sola en el mes natural cuando no hay ninguno declarado.
    */
  const userAnchor = userMonthAnchorContaining(todayDayStr(), cycleStartDay);
  /*
   * Los avisos de «esta tarjeta sigue en mes natural» los dispara ahora el
   * PERFIL y no un clic. Es un cambio de alcance, no de redacción: antes el
   * descuadre entre tarjetas lo provocaba el usuario al pulsar un chip, y a
   * partir de aquí lo provoca su ajuste — así que sin el aviso la pantalla
   * mentiría por omisión a quien nunca eligió nada.
   */
  const monthIsCycle = userMonthIsCycle(cycleStartDay);
  const { dateFrom, dateTo } = useMemo(
    () =>
      boundsForUserPeriod(period, userAnchor, { cycleStartDay, customFrom, customTo }),
    [period, customFrom, customTo, userAnchor, cycleStartDay],
  );
  // Del MISMO ancla que el rango de arriba: leer el reloj por segunda vez
  // (`new Date().getFullYear()`) dejaba el chart pidiendo un año distinto del
  // que resumen los KPIs justo encima en la franja de cambio de año. En ciclo,
  // el ancla es la del ciclo (en enero con D>1 puede ser el año anterior).
  const currentYear = Number(
    userAnchor.slice(0, 4),
  );

  /*
   * C4 — Con el preset activo, `cycle: true` hace que el BACKEND bucketee y
   * acote por el ciclo del usuario. El día no viaja: lo lee el servidor del
   * perfil. Entra en la query key (`normalizeQuery` toma todas las claves), así
   * que activar el preset no sirve datos cacheados del mes natural.
   */
  // PHASE-47 — el flag lo dispara el PERFIL. La guarda no es redundante: sin
  // ella, si el usuario vuelve al mes natural desde otro dispositivo, se
  // enviaría `cycle=true` con bounds de mes natural y el backend responde 422.
  const cycleParam = userMonthIsCycle(cycleStartDay) ? { cycle: true } : {};
  // PHASE-14.4: cuando convertAll=true pedimos `target_currency` y el
  // backend convierte cada tx con la tasa de su día. Cuando false,
  // comportamiento legacy filtrado por moneda activa.
  const summaryParams = convertAll
    ? { target_currency: currency, date_from: dateFrom, date_to: dateTo, ...cycleParam }
    : { currency, date_from: dateFrom, date_to: dateTo, ...cycleParam };
  // PHASE-41 — en custom, el chart mensual se acota al rango (bordes parciales)
  // para cuadrar con los KPIs; en mes/año, por año natural.
  // C4 — el ciclo va por AÑO (los 12 ciclos que abren en ese año) más
  // `cycle: true`: así el chart pinta el histórico entero en barras de ciclo,
  // que es lo que el usuario pidió, y no sólo el ciclo en curso.
  const monthlyParams =
    userMonthIsCycle(cycleStartDay) && period !== 'custom'
      ? convertAll
        ? { target_currency: currency, year: currentYear, cycle: true }
        : { currency, year: currentYear, cycle: true }
      : period === 'custom'
        ? convertAll
          ? { target_currency: currency, date_from: dateFrom, date_to: dateTo }
          : { currency, date_from: dateFrom, date_to: dateTo }
        : convertAll
          ? { target_currency: currency, year: currentYear }
          : { currency, year: currentYear };
  const byCategoryParams = convertAll
    ? {
        target_currency: currency,
        date_from: dateFrom,
        date_to: dateTo,
        ...(donutKind === 'all' ? {} : { kind: donutKind }),
      }
    : {
        currency,
        date_from: dateFrom,
        date_to: dateTo,
        ...(donutKind === 'all' ? {} : { kind: donutKind }),
      };
  const topExpensesParams = convertAll
    ? {
        target_currency: currency,
        date_from: dateFrom,
        date_to: dateTo,
        limit: TOP_EXPENSES_LIMIT,
      }
    : {
        currency,
        date_from: dateFrom,
        date_to: dateTo,
        limit: TOP_EXPENSES_LIMIT,
      };

  // PHASE-37.6 (parity 37.3/37.4) — gasto estructural (impacto de puntuales) +
  // proyección fin de mes + runway. El outlook no tiene rango (mes en curso).
  const structureParams = convertAll
    ? { target_currency: currency, date_from: dateFrom, date_to: dateTo }
    : { currency, date_from: dateFrom, date_to: dateTo };
  const outlookParams = convertAll ? { target_currency: currency } : { currency };

  const summaryQuery = useDashboardSummary(summaryParams);

  // PHASE-47.E — la diferencia entre el donut (que mantiene lo aplazado) y los
  // KPI (que lo excluyen), dicha en voz alta. La redacción vive en
  // `@crisol/ui` para que las dos pantallas no la cuenten distinto.
  // Sólo cuando el donut está enseñando GASTO: el aviso habla de gasto
  // aplazado, y pintado bajo el donut de ingresos sería un pie de foto que no
  // describe lo que hay encima.
  // `all` también lo enseña: el donut incluye el gasto y el aviso lo explica.
  // El que se excluye es `income`, donde sería un pie de foto que no describe
  // lo que hay encima.
  const deferredNotice =
    donutKind === 'income'
      ? null
      : deferredBreakdownNotice(summaryQuery.data?.deferred_expenses, currency);
  const monthlyQuery = useDashboardByMonth(monthlyParams);
  const byCategoryQuery = useDashboardByCategory(byCategoryParams);
  const topExpensesQuery = useDashboardTopExpenses(topExpensesParams);
  const structureQuery = useExpenseStructure(structureParams);
  const outlookQuery = useMonthOutlook(outlookParams);

  const refreshing =
    summaryQuery.isFetching ||
    monthlyQuery.isFetching ||
    byCategoryQuery.isFetching ||
    topExpensesQuery.isFetching;

  function handleRefresh() {
    void summaryQuery.refetch();
    void monthlyQuery.refetch();
    void byCategoryQuery.refetch();
    void topExpensesQuery.refetch();
  }

  async function handleLogout() {
    try {
      if (refreshToken) {
        await authApi.logout(refreshToken);
      }
    } finally {
      clearAuth();
      /*
       * PHASE-47 — vaciar el caché al cerrar sesión. Las query keys no llevan
       * la identidad del usuario, así que sin esto el siguiente hereda las
       * respuestas del anterior mientras duren sus `staleTime` — incluido su
       * día de corte, que hace que la app pida «por ciclo» para quien no ha
       * declarado ninguno y reciba un 422.
       */
      queryClient.clear();
    }
  }

  const expensesByCategory = byCategoryQuery.data ?? [];
  const hasError =
    summaryQuery.isError ||
    monthlyQuery.isError ||
    byCategoryQuery.isError ||
    topExpensesQuery.isError;

  return (
    <View style={styles.container}>
      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={handleRefresh} />}
      >
        <View style={styles.header}>
          <View style={{ flex: 1 }}>
            <Text style={styles.greeting}>Hola, {user?.display_name ?? 'usuario'}</Text>
            <Text style={styles.subtitle}>Análisis financiero</Text>
          </View>
          <View style={styles.headerActions}>
            <Link href="/(modules)/personal-finance/budgets" asChild>
              <Pressable style={styles.headerButton}>
                <Text style={styles.headerButtonText}>Presupuestos</Text>
              </Pressable>
            </Link>
            <Link href="/(modules)/personal-finance/fixed-expenses" asChild>
              <Pressable style={styles.headerButton}>
                <Text style={styles.headerButtonText}>Gastos fijos</Text>
              </Pressable>
            </Link>
            <Link href="/(modules)/personal-finance/categories" asChild>
              <Pressable style={styles.headerButton}>
                <Text style={styles.headerButtonText}>Categorías</Text>
              </Pressable>
            </Link>
            <Link href="/(modules)/personal-finance/accounts" asChild>
              <Pressable style={styles.headerButton}>
                <Text style={styles.headerButtonText}>Cuentas</Text>
              </Pressable>
            </Link>
            {/*
              C2 móvil — Sin este enlace la pantalla de Ajustes existe y está
              registrada en el Stack, pero NADA navega a ella: el usuario que
              sólo usa el móvil no podría configurar su día nunca, así que el
              chip «Mi ciclo» tampoco aparecería jamás. La feature entera queda
              inerte por una ruta sin puerta.
            */}
            <Link href="/(modules)/personal-finance/settings" asChild>
              <Pressable style={styles.headerButton}>
                <Text style={styles.headerButtonText}>Ajustes</Text>
              </Pressable>
            </Link>
            <Pressable onPress={handleLogout} style={styles.logoutButton}>
              <Text style={styles.logoutText}>Salir</Text>
            </Pressable>
          </View>
        </View>

        <View style={styles.currencyRow}>
          <CurrencyPicker
            value={currency}
            onChange={setCurrency}
            currencies={currenciesQuery.data}
          />
          <Pressable
            onPress={() => setConvertAll(!convertAll)}
            style={({ pressed }) => [
              styles.convertChip,
              convertAll && styles.convertChipActive,
              pressed && { opacity: 0.7 },
            ]}
            accessibilityRole="switch"
            accessibilityState={{ checked: convertAll }}
          >
            <Text
              style={[
                styles.convertChipText,
                convertAll && styles.convertChipTextActive,
              ]}
            >
              {convertAll ? '✓ Convertir todo' : 'Convertir todo'}
            </Text>
          </Pressable>
        </View>
        {/* C3a — «Mi ciclo» se pide siempre; el toggle lo filtra si no hay
            ajuste (guarda por verdad dentro del componente). */}
        <PeriodToggle
          value={period}
          onChange={handlePeriodChange}
          options={['month', 'year', 'custom']}
        />
        {period === 'custom' ? (
          <View style={styles.customRow}>
            <DateInput
              value={customFrom ?? ''}
              maximumDate={customTo ? new Date(customTo) : undefined}
              onChange={(from) => handleCustomRangeChange(from, customTo ?? '')}
            />
            <Text style={styles.customDash}>–</Text>
            <DateInput
              value={customTo ?? ''}
              minimumDate={customFrom ? new Date(customFrom) : undefined}
              onChange={(to) => handleCustomRangeChange(customFrom ?? '', to)}
            />
          </View>
        ) : null}

        {hasError ? (
          <View style={{ marginBottom: spacing.md }}>
            <ErrorState
              description="No se pudieron cargar algunas secciones del análisis. Las cifras pueden estar incompletas."
              onRetry={handleRefresh}
              retrying={refreshing}
            />
          </View>
        ) : null}

        <BalancesCard />
        <DebtHealthCard />
        <NetworthEvolutionCard />
        {/* PHASE-47 — de las tres tarjetas que este comentario enumeraba, sólo
            la evolución de patrimonio sigue contando el mes NATURAL: su serie
            (`position-history`) son 12 meses de calendario fijos y no recibe el
            día. Sus cifras dejan de cuadrar con el resto de la pantalla A
            PROPÓSITO, y una diferencia que nadie nombra se lee como un fallo.
            La redacción vive en `@crisol/ui`: escrita dos veces, divergiría. */}
        <NaturalMonthNotice visible={monthIsCycle} testID="natural-month-notice-networth" />
        <KpiCards summary={summaryQuery.data} isLoading={summaryQuery.isLoading} />
        <SavingsRateCard summary={summaryQuery.data} />
        <MonthOutlookCard data={outlookQuery.data} currency={currency} />
        {/* PHASE-47 — aquí iba el aviso «esta tarjeta cuenta el mes de
            siempre». `get_month_outlook` ya corta por el mes del usuario, así
            que la frase afirmaba lo contrario de lo que hace el código: el
            usuario leía «quedan 24 días» —correcto, hasta SU corte— y debajo
            una explicación que lo desmentía. Una premisa escrita que caducó en
            el mismo commit que la migró. */}
        <MonthlyChart
          data={monthlyQuery.data}
          isLoading={monthlyQuery.isLoading}
          currency={currency}
          // Con el mes del usuario, los buckets son sus ciclos y no meses.
          cycleStartDay={monthIsCycle ? cycleStartDay : undefined}
        />
        <CategoryDonut
          data={byCategoryQuery.data}
          currency={currency}
          isLoading={byCategoryQuery.isLoading}
          kind={donutKind}
          onKindChange={setDonutKind}
          exceptionalByCategory={structureQuery.data?.exceptional_by_category}
        />
        {/* PHASE-47.E — el donut MANTIENE las compras aplazadas (el gasto se
            hizo) y los KPI de arriba las excluyen (el dinero no salió). Sin
            este aviso, quien sume el donut se encuentra cientos de euros de
            más que el KPI y no tiene forma de saber por qué. */}
        {deferredNotice ? (
          <Text
            testID="deferred-notice"
            style={{
              fontSize: fontSize.xs,
              color: colors.textMuted,
              lineHeight: 18,
              paddingHorizontal: spacing.md,
              marginBottom: spacing.md,
            }}
          >
            {deferredNotice}
          </Text>
        ) : null}
        <TopExpensesList
          data={topExpensesQuery.data}
          currency={currency}
          isLoading={topExpensesQuery.isLoading}
        />
        <SmartInsights
          summary={summaryQuery.data}
          expensesByCategory={expensesByCategory}
          structure={structureQuery.data}
          outlook={outlookQuery.data}
          currency={currency}
        />
        {/* PHASE-47 — ídem. Las cuatro entradas de `SmartInsights` (resumen,
            desglose, estructura de gasto y la propia proyección) cortan ya por
            el mes del usuario. */}
      </ScrollView>

      <FabLink
        href="/(modules)/personal-finance/transaction/new"
        ariaLabel="Añadir transacción"
      />
    </View>
  );
}

/**
 * C3a — Aviso «esta tarjeta cuenta el mes de siempre», con la redacción única
 * de `@crisol/ui`. Se pinta sólo con el preset de ciclo activo.
 */
function NaturalMonthNotice({ visible, testID }: { visible: boolean; testID: string }) {
  if (!visible) return null;
  return (
    <Text testID={testID} style={styles.naturalNotice}>
      {NATURAL_MONTH_NOTICE}
    </Text>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  naturalNotice: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
    lineHeight: 18,
    paddingHorizontal: spacing.md,
    marginTop: -spacing.xs,
    marginBottom: spacing.md,
  },
  content: { padding: spacing.md, paddingBottom: spacing.xl },
  customRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    marginBottom: spacing.md,
  },
  customDash: { color: colors.textMuted, fontSize: fontSize.sm },
  header: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    marginBottom: spacing.md,
    gap: spacing.sm,
  },
  greeting: { fontSize: fontSize.xl, fontWeight: fontWeight.semibold, color: colors.text },
  subtitle: { fontSize: fontSize.sm, color: colors.textMuted, marginTop: 2 },
  headerActions: { flexDirection: 'row', gap: spacing.xs, alignItems: 'center' },
  currencyRow: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: spacing.sm,
    marginBottom: spacing.md,
  },
  convertChip: {
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.md,
    borderRadius: 999,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  convertChipActive: {
    backgroundColor: colors.primarySoft,
    borderColor: colors.primary,
  },
  convertChipText: {
    fontSize: fontSize.sm,
    color: colors.text,
    fontWeight: fontWeight.medium,
  },
  convertChipTextActive: {
    color: colors.primary,
    fontWeight: fontWeight.semibold,
  },
  headerButton: {
    paddingVertical: 6,
    paddingHorizontal: spacing.sm,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: 6,
  },
  headerButtonText: {
    fontSize: fontSize.sm,
    color: colors.text,
    fontWeight: fontWeight.medium,
  },
  logoutButton: {
    paddingVertical: 6,
    paddingHorizontal: spacing.sm,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: 6,
  },
  logoutText: { fontSize: fontSize.sm, color: colors.danger, fontWeight: fontWeight.medium },
});
