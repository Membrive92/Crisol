'use client';

import { colors, fontSize, spacing } from '@crisol/ui';
import type { AnalysisRun, DuPontDecomposition, MetricResult } from '@crisol/types';

import { Card, CardTitle } from '@/components/ui/card';
import { Segmented } from '@/components/ui/segmented';

import { DegradedPanel, InlineNotice } from './degraded-panel';
import { groupRow, metricRow, missingRow, type MetricRowOptions } from './metric-rows';
import type { CatalogIndex, MetricIndex } from './metric-index';
import { YearMatrix, type MatrixRow } from './year-matrix';

/**
 * Las familias, en el orden de las hojas 5 a 9 del cuaderno del usuario, con las
 * métricas que el motor calcula en cada una.
 */
const FAMILIES = [
  {
    key: 'liquidez',
    label: 'Liquidez',
    metrics: ['L1', 'L2', 'L3', 'L4'],
    note: 'El cuaderno pide ratio corriente, prueba ácida y ratio de caja. El muro de vencimientos (L4) lo añade el motor: es el mecanismo real por el que una empresa quiebra —no poder refinanciar— y los otros tres no lo miran.',
  },
  {
    key: 'actividad',
    label: 'Actividad',
    metrics: ['A1', 'A2', 'A3', 'A4', 'A5'],
    note: 'Ninguna tiene banda absoluta, y es deliberado: un plazo de cobro de 45 días es excelente en retail y pésimo en software. Lo que informa aquí es la deriva, no el nivel. Ojo: el motor usa saldos MEDIOS (t y t−1); tu cuaderno usa el saldo de cierre, así que los números no coincidirán exactamente.',
  },
  {
    key: 'solvencia',
    label: 'Solvencia y deuda',
    metrics: ['S1', 'S2', 'S3', 'S4', 'S4b', 'S5', 'S6', 'S7', 'S8'],
    note: 'S2 usa EBIT (devengo, maquillable) y S6 usa caja generada. Si S2 sale verde y S6 rojo, el devengo está mintiendo. Igual con S4 (sobre EBITDA) y S4b (sobre EBIT): en negocios con mucha amortización, el EBITDA infla la capacidad de repago aparente. El ratio de endeudamiento (S7) usa la banda 1-2 de tu cuaderno, calibrada para negocios con activo tangible: en financieras se muestra sin semáforo, porque allí el apalancamiento es el negocio.',
  },
  {
    key: 'rentabilidad',
    label: 'Rentabilidad',
    metrics: ['R1', 'R2', 'R3', 'R4', 'R5', 'R6', 'R7', 'R8', 'R9', 'R9b', 'R10', 'DUPONT_EM'],
    note: 'Margen bruto, margen neto y apalancamiento financiero salen sin banda: los cortes de tu cuaderno (40 %, 10 %, ≤3) son razonables como regla general, pero dependen tanto del sector que el motor prefiere no pintar un semáforo global.',
  },
  {
    key: 'dupont',
    label: 'DuPont',
    metrics: [],
    note: '',
  },
] as const;

/** Lo que el cuaderno pide y el motor no calcula. Se lista en gris con motivo:
 *  omitirlo se leería como «no aplica», y lo que pasa es que no existe. */
const MISSING_BY_FAMILY: Record<string, { key: string; label: string; reason: string }[]> = {};

export interface TabRatiosProps {
  run: AnalysisRun;
  index: MetricIndex;
  catalog: CatalogIndex;
  sub: string;
  onSubChange: (key: string) => void;
}

export function TabRatios({ run, index, catalog, sub, onSubChange }: TabRatiosProps) {
  const years = run.years_covered;
  const verdictYear = years[years.length - 1];
  const options: MetricRowOptions = {
    index,
    catalog,
    thresholdsUsed: run.thresholds_used,
  };

  const family = FAMILIES.find((f) => f.key === sub) ?? FAMILIES[0];

  const segmentedOptions = FAMILIES.map((f) => {
    if (f.key === 'dupont') return { key: f.key, label: f.label };
    const computable = f.metrics.some((key) =>
      index.series(key).some((m) => m && m.status !== 'not_computable'),
    );
    return {
      key: f.key,
      label: f.label,
      degraded: !computable,
      degradedHint: 'ninguna métrica de este bloque es calculable con los datos de este valor',
    };
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.lg }}>
      <Segmented
        label="Familia de ratios"
        value={family.key}
        onChange={onSubChange}
        options={segmentedOptions}
      />

      {family.key === 'dupont' ? (
        <DuPontSection run={run} catalog={catalog} />
      ) : (
        <Card>
          <CardTitle size="sm">{family.label}</CardTitle>
          <div style={{ marginTop: spacing.md, display: 'grid', gap: spacing.md }}>
            <InlineNotice>{family.note}</InlineNotice>
            <YearMatrix
              years={years}
              rows={buildFamilyRows(family.key, [...family.metrics], options, years)}
              verdictYear={verdictYear}
              firstColumnLabel="Métrica"
              legend={
                <>
                  <div>
                    <strong>—</strong> no calculable: bajo la etiqueta se explica por qué
                  </div>
                  <div>
                    <strong>*</strong> calculada con un input degradado (normalmente el primer
                    ejercicio, sin año anterior con el que promediar)
                  </div>
                  <div>
                    Una celda <strong>gris</strong> es un valor sin banda: el motor no tiene un
                    corte absoluto que aplicar. No significa que esté sano.
                  </div>
                </>
              }
            />
          </div>
        </Card>
      )}
    </div>
  );
}

function buildFamilyRows(
  familyKey: string,
  metrics: string[],
  options: MetricRowOptions,
  years: number[],
): MatrixRow[] {
  const rows = metrics.map((key) => metricRow(key, options));
  const missing = MISSING_BY_FAMILY[familyKey] ?? [];
  if (missing.length === 0) return rows;
  return [
    ...rows,
    groupRow(`${familyKey}-missing`, 'Tu cuaderno lo pide y el motor no lo calcula'),
    ...missing.map((m) => missingRow(m.key, m.label, m.reason, years)),
  ];
}

function DuPontSection({ run, catalog }: { run: AnalysisRun; catalog: CatalogIndex }) {
  const dupont = run.scores_detail.base_ratios.dupont ?? [];
  if (dupont.length === 0) {
    return (
      <DegradedPanel
        title="Sin descomposición DuPont"
        reason="Este análisis no trae la descomposición del ROE. Vuelve a ejecutarlo para obtenerla."
      />
    );
  }

  const years = dupont.map((d) => d.fiscal_year);
  const pointFor = (year: number) => dupont.find((d) => d.fiscal_year === year);

  // Índice sobre la propia descomposición: sus MetricResult son los MISMOS
  // objetos que emite la capa 1, así que la fila de aquí y la de la matriz de
  // Rentabilidad no pueden divergir.
  const FACTORS: Record<string, (d: DuPontDecomposition) => MetricResult> = {
    R4: (d) => d.net_margin,
    A4: (d) => d.asset_turnover,
    DUPONT_EM: (d) => d.equity_multiplier,
    DUPONT_OM: (d) => d.operating_margin,
    DUPONT_TAX: (d) => d.tax_effect,
    DUPONT_FIN: (d) => d.financial_cost,
  };

  const options: MetricRowOptions = {
    index: {
      get: (key, year) => {
        const point = pointFor(year);
        const pick = FACTORS[key];
        return point && pick ? pick(point) : undefined;
      },
      series: (key) =>
        years.map((year) => {
          const point = pointFor(year);
          const pick = FACTORS[key];
          return point && pick ? pick(point) : undefined;
        }),
      years,
      keys: Object.keys(FACTORS),
    },
    catalog,
    thresholdsUsed: run.thresholds_used,
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.lg }}>
      <Card>
        <CardTitle size="sm">DuPont de tres factores</CardTitle>
        <div style={{ marginTop: spacing.md, display: 'grid', gap: spacing.md }}>
          <p style={{ margin: 0, color: colors.textMuted, fontSize: fontSize.sm, lineHeight: 1.6 }}>
            <strong style={{ color: colors.text }}>
              ROE = margen neto × rotación de activos × apalancamiento financiero
            </strong>
            . Dice QUÉ movió el ROE: uno que sube sólo por el apalancamiento no es mejora del
            negocio, es deuda.
          </p>
          <YearMatrix
            years={years}
            rows={[
              metricRow('R4', options),
              metricRow('A4', options),
              metricRow('DUPONT_EM', options),
              checkRow('check-3', dupont, (d) => d.check_three),
            ]}
            firstColumnLabel="Factor"
          />
        </div>
      </Card>

      <Card>
        <CardTitle size="sm">DuPont extendido (cinco factores)</CardTitle>
        <div style={{ marginTop: spacing.md, display: 'grid', gap: spacing.md }}>
          <p style={{ margin: 0, color: colors.textMuted, fontSize: fontSize.sm, lineHeight: 1.6 }}>
            <strong style={{ color: colors.text }}>
              ROE = margen operativo × efecto fiscal × coste financiero × rotación ×
              apalancamiento
            </strong>
            . Desdobla el margen neto en de dónde sale: cuánto gana el negocio, cuánto se lleva la
            financiación y cuánto Hacienda.
          </p>
          <YearMatrix
            years={years}
            rows={[
              metricRow('DUPONT_OM', options),
              metricRow('DUPONT_TAX', options),
              metricRow('DUPONT_FIN', options),
              metricRow('A4', options),
              metricRow('DUPONT_EM', options),
              checkRow('check-5', dupont, (d) => d.check_five),
            ]}
            firstColumnLabel="Factor"
          />
          <InlineNotice>
            El margen operativo usa el <strong>EBIT reportado</strong>, no el limpio de deterioros
            y plusvalías que emplea R3. Es lo que hace que la identidad cierre: con el limpio
            arriba y el reportado en el coste financiero, el EBIT no se cancela y el ROE
            reconstruido sale inflado justo en los años con deterioros.
          </InlineNotice>
        </div>
      </Card>
    </div>
  );
}

/**
 * La fila de comprobación del cuaderno: el producto de los factores menos el
 * ROE. Debe ser 0.
 *
 * Un `null` se pinta como <strong>no verificable</strong>, nunca como cuadrado:
 * significa que faltaba algún factor (a McDonald's le pasa, con patrimonio neto
 * negativo), y un cuadre que no se ha podido comprobar no es un cuadre superado.
 */
function checkRow(
  key: string,
  dupont: DuPontDecomposition[],
  pick: (d: DuPontDecomposition) => string | null,
): MatrixRow {
  return {
    key,
    label: 'Comprobación',
    hint: 'producto de los factores menos el ROE: debe ser cero',
    emphasis: true,
    cells: dupont.map((point) => {
      const raw = pick(point);
      if (raw === null) {
        return {
          text: 'no verificable',
          title: 'falta algún factor, así que la identidad no se puede comprobar',
        };
      }
      const value = Number(raw);
      const closes = Math.abs(value) < 1e-12;
      return {
        text: closes ? '0' : value.toExponential(1),
        color: closes ? colors.success : colors.danger,
        title: closes
          ? 'la identidad cierra'
          : 'la identidad NO cierra: hay un problema en los datos o en una fórmula',
      };
    }),
  };
}
