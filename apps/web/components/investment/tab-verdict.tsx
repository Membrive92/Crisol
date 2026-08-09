'use client';

import { useState } from 'react';

import { colors, fontSize, fontWeight, questionEvidence, radius, spacing } from '@crisol/ui';
import type {
  AnalysisRun,
  CanonicalItemDefinition,
  FinancialStatement,
  QuestionVerdict,
  SafetyLabel,
} from '@crisol/types';

import { Card, CardTitle } from '@/components/ui/card';
import { Segmented } from '@/components/ui/segmented';

import { BandChip, bandColors } from './band-chip';
import { DegradedPanel, InlineNotice } from './degraded-panel';
import { FlagList } from './flag-list';
import { SignalTable } from './signal-table';
import type { CatalogIndex } from '@crisol/ui';

const SAFETY: Record<SafetyLabel, { label: string; fg: string; bg: string }> = {
  conservative: { label: 'Conservador', fg: colors.success, bg: colors.successSoft },
  watch: { label: 'Vigilar', fg: colors.warning, bg: colors.warningSoft },
  avoid: { label: 'Evitar', fg: colors.danger, bg: colors.dangerSoft },
};

/** Las cinco condiciones que exige el perfil Conservador, tal y como las
 *  evalúa `_safety_profile` en el motor. Se imprimen SIEMPRE, cumplidas o no:
 *  un sello sin sus reglas no es auditable. */
const CONSERVATIVE_RULES = [
  'M-Score en verde',
  "Z''-Score en verde",
  'X-Score en verde',
  'F-Score ≥ 7',
  'Accruals en verde',
] as const;

/** Las cuatro condiciones que fuerzan «Evitar». */
const AVOID_RULES = [
  'M-Score y accruals ambos en rojo (manipulación probable)',
  "Z''-Score en rojo (riesgo de insolvencia)",
  'X-Score en rojo (riesgo de quiebra)',
  'dividendo financiado con deuda o emisión',
] as const;

/** Las 10 partidas núcleo con las que el motor calcula la completitud. */
const CORE_ITEMS = [
  'revenue',
  'ebit',
  'net_income',
  'cfo',
  'capex',
  'dividends_paid',
  'total_assets',
  'equity',
  'current_assets',
  'current_liabilities',
] as const;

export interface TabVerdictProps {
  run: AnalysisRun;
  catalog: CatalogIndex;
  statements: FinancialStatement[] | undefined;
  items: CanonicalItemDefinition[] | undefined;
  sub: string;
  onSubChange: (key: string) => void;
}

export function TabVerdict({
  run,
  catalog,
  statements,
  items,
  sub,
  onSubChange,
}: TabVerdictProps) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.lg }}>
      <Segmented
        label="Secciones del veredicto"
        value={sub}
        onChange={onSubChange}
        options={[
          { key: 'dictamen', label: 'Dictamen' },
          { key: 'datos', label: 'Confianza y datos' },
        ]}
      />
      {sub === 'datos' ? (
        <ConfidenceSection run={run} statements={statements} items={items} />
      ) : (
        <DictamenSection run={run} catalog={catalog} />
      )}
    </div>
  );
}

// ── Dictamen ──────────────────────────────────────────────────────────

function DictamenSection({ run, catalog }: { run: AnalysisRun; catalog: CatalogIndex }) {
  const profile = run.verdict.safety_profile;
  const safety = SAFETY[profile.label];
  const blocking = profile.blocking_reasons;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.lg }}>
      <Card style={{ display: 'flex', flexDirection: 'column', gap: spacing.md }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: spacing.md,
            flexWrap: 'wrap',
          }}
        >
          <CardTitle>Perfil de seguridad</CardTitle>
          <span
            style={{
              color: safety.fg,
              backgroundColor: safety.bg,
              borderRadius: radius.sm,
              padding: `4px ${spacing.md}px`,
              fontSize: fontSize.sm,
              fontWeight: fontWeight.bold,
            }}
          >
            {safety.label}
          </span>
        </div>

        <p style={{ margin: 0, color: colors.textMuted, fontSize: fontSize.sm, lineHeight: 1.5 }}>
          El perfil no es una nota media: sale de reglas booleanas sobre los scores forenses.
          Estas son, con lo que ha pasado en este análisis.
        </p>

        <RuleChecklist
          title="Se evita si se cumple CUALQUIERA de estas"
          rules={AVOID_RULES.map((rule) => ({
            text: rule,
            met: blocking.includes(rule),
          }))}
          metIsBad
        />

        <RuleChecklist
          title="Es conservador sólo si se cumplen LAS CINCO"
          rules={CONSERVATIVE_RULES.map((rule) => ({
            text: rule,
            // `blocking_reasons` de un perfil «watch» lista lo que NO se cumple,
            // con el texto en negativo («M-Score no está en verde»).
            met: profile.label === 'conservative' ? true : !blocking.some((r) => isNegationOf(r, rule)),
          }))}
        />

        {blocking.length > 0 ? (
          <InlineNotice>
            <strong>{profile.label === 'avoid' ? 'Motivos: ' : 'Falta para Conservador: '}</strong>
            {blocking.join('; ')}.
          </InlineNotice>
        ) : null}
      </Card>

      <Card style={{ display: 'flex', flexDirection: 'column', gap: spacing.md }}>
        <CardTitle>Las cuatro preguntas</CardTitle>
        <InlineNotice>
          Regla del semáforo: <strong>rojo</strong> si hay ≥1 señal roja · <strong>ámbar</strong>{' '}
          si hay ≥2 ámbar · <strong>verde</strong> en el resto. Una señal sin banda o no
          calculable no cuenta ni a favor ni en contra — por eso cada pregunta declara cuántas
          pudo evaluar.
        </InlineNotice>
        {run.verdict.questions.map((question) => (
          <QuestionBlock
            key={question.key}
            question={question}
            catalog={catalog}
            thresholdsUsed={run.thresholds_used}
          />
        ))}
      </Card>

      <StressCard run={run} />

      <Card style={{ display: 'flex', flexDirection: 'column', gap: spacing.md }}>
        <CardTitle>Banderas</CardTitle>
        <FlagList flags={run.flags} emptyLabel="El motor no ha encendido ninguna bandera." />
      </Card>

      <Card style={{ display: 'flex', flexDirection: 'column', gap: spacing.sm }}>
        <CardTitle size="sm">Alcance: lo que este informe NO cubre</CardTitle>
        <ul
          style={{
            margin: 0,
            paddingLeft: spacing.lg,
            color: colors.textMuted,
            fontSize: fontSize.sm,
            lineHeight: 1.6,
          }}
        >
          <li>
            <strong>Valoración.</strong> Ni PER, ni precio/ventas, ni precio/valor contable, ni
            precio/caja libre, ni EV/EBITDA, ni descuento de dividendos. Todos necesitan precio
            de mercado, y el motor no lo recibe a propósito: un score que se mueve con la
            cotización no sería reproducible al reejecutar un análisis antiguo.
          </li>
          <li>
            <strong>Comparación con el sector.</strong> El sector sólo elige umbrales; no hay
            fuente de múltiplos de comparables.
          </li>
          <li>
            <strong>Reexpresiones.</strong> Se detectan y se listan aparte, pero todavía no
            entran en el dictamen.
          </li>
          <li>
            <strong>Retribución de directivos y calendario de vencimientos.</strong> Viven en el
            proxy statement y en las notas, no en el 10-K estructurado que se ingiere.
          </li>
        </ul>
      </Card>

      <p style={{ margin: 0, color: colors.textSubtle, fontSize: fontSize.xs, lineHeight: 1.6 }}>
        Motor {run.engine_version} · umbrales {run.thresholds_version} · ejercicios{' '}
        {run.years_covered.join(', ')} · análisis del{' '}
        {new Date(run.run_date).toLocaleString('es-ES')}
      </p>
    </div>
  );
}

/** ¿El motivo bloqueante es la negación de esta regla? El motor los escribe en
 *  negativo («M-Score no está en verde») y la regla está en positivo. */
function isNegationOf(reason: string, rule: string): boolean {
  const head = rule.split(' ')[0] ?? '';
  return head.length > 0 && reason.startsWith(head);
}

function RuleChecklist({
  title,
  rules,
  metIsBad = false,
}: {
  title: string;
  rules: { text: string; met: boolean }[];
  metIsBad?: boolean;
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.xs }}>
      <span
        style={{
          color: colors.textMuted,
          fontSize: fontSize.xs,
          fontWeight: fontWeight.semibold,
          textTransform: 'uppercase',
          letterSpacing: '0.04em',
        }}
      >
        {title}
      </span>
      <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'grid', gap: 2 }}>
        {rules.map((rule) => {
          const bad = metIsBad ? rule.met : !rule.met;
          return (
            <li
              key={rule.text}
              style={{
                display: 'flex',
                gap: spacing.sm,
                fontSize: fontSize.sm,
                color: bad ? colors.danger : colors.textMuted,
              }}
            >
              <span aria-hidden style={{ color: bad ? colors.danger : colors.success }}>
                {rule.met ? (metIsBad ? '✕' : '✓') : metIsBad ? '✓' : '✕'}
              </span>
              <span>{rule.text}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/**
 * Lo único que un run anterior a PHASE-44.9 sabe decir de una pregunta.
 *
 * Sin `signals[]` no hay desglose, pero `red_signals` y `amber_signals` SÍ están
 * — son las claves crudas del motor, y hasta ahora no se pintaban en ninguna
 * parte de la web. Traducirlas con el catálogo las hace legibles sin inventar
 * nada: no hay valor, ni banda, ni motivo, y no se fingen.
 *
 * Se dice además que el veredicto no es auditable. Es la mitad honesta del
 * arreglo: sin saber cuántas señales se evaluaron, un verde puede ser salud o
 * puede ser ausencia de prueba, y de un run viejo no hay forma de distinguirlo.
 */
function LegacySignals({
  question,
  catalog,
}: {
  question: QuestionVerdict;
  catalog: CatalogIndex;
}) {
  const label = (key: string) => catalog.definition(key)?.label ?? key;
  const groups = [
    { keys: question.red_signals, color: colors.danger, name: 'En rojo' },
    { keys: question.amber_signals, color: colors.warning, name: 'En ámbar' },
  ].filter((g) => g.keys.length > 0);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.xs }}>
      <span style={{ color: colors.textMuted, fontSize: fontSize.xs, lineHeight: 1.5 }}>
        Este análisis lo produjo un motor anterior, que no registraba qué señales se evaluaron.
        El veredicto de abajo <strong>no es auditable</strong>: vuelve a ejecutar el análisis
        para ver el desglose.
      </span>
      {groups.map((group) => (
        <span key={group.name} style={{ color: colors.textMuted, fontSize: fontSize.xs }}>
          <strong style={{ color: group.color }}>{group.name}:</strong>{' '}
          {group.keys.map(label).join(' · ')}
        </span>
      ))}
      {groups.length === 0 ? (
        <span style={{ color: colors.textMuted, fontSize: fontSize.xs }}>
          No registró ninguna señal en rojo ni en ámbar.
        </span>
      ) : null}
    </div>
  );
}

function QuestionBlock({
  question,
  catalog,
  thresholdsUsed,
}: {
  question: QuestionVerdict;
  catalog: CatalogIndex;
  thresholdsUsed: AnalysisRun['thresholds_used'];
}) {
  const [open, setOpen] = useState(false);
  const { fg, bg } = bandColors(question.verdict);

  // `signals` AUSENTE (motor < 1.1.0) no es `signals` vacío: el desglose no se
  // registraba. El tri-estado vive en `@crisol/ui` porque esta misma regla la
  // necesita también el hero.
  const signals = question.signals;
  const evidence = questionEvidence(question);
  // Sin desglose no hay nada detrás de la flecha. Ofrecerla igualmente es la
  // trampa que reportó el usuario: se despliega para encontrar un error.
  const expandable = signals !== undefined && signals.length > 0;
  const muted = evidence !== 'evaluated';

  const title = (
    <span style={{ color: colors.text, fontSize: fontSize.sm, fontWeight: fontWeight.semibold }}>
      {expandable ? (open ? '▾ ' : '▸ ') : ''}
      {question.question}
    </span>
  );
  const chip = (
    <BandChip
      band={muted ? null : question.verdict}
      label={
        evidence === 'no-evidence'
          ? 'Sin evidencia'
          : evidence === 'not-recorded'
            ? 'No auditable'
            : undefined
      }
    />
  );
  const headerLayout = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.sm,
    width: '100%',
  } as const;

  return (
    <div
      style={{
        borderRadius: radius.md,
        backgroundColor: muted ? colors.surfaceMuted : bg,
        borderLeft: `3px solid ${muted ? colors.textMuted : fg}`,
        padding: spacing.md,
        display: 'flex',
        flexDirection: 'column',
        gap: spacing.sm,
      }}
    >
      {expandable ? (
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          style={{
            ...headerLayout,
            background: 'none',
            border: 'none',
            padding: 0,
            cursor: 'pointer',
            textAlign: 'left',
          }}
        >
          {title}
          {chip}
        </button>
      ) : (
        <div style={headerLayout}>
          {title}
          {chip}
        </div>
      )}

      {evidence === 'not-recorded' ? (
        <LegacySignals question={question} catalog={catalog} />
      ) : (
        <span style={{ color: colors.textMuted, fontSize: fontSize.xs }}>
          {question.evaluated_count} señales evaluadas · {question.unavailable_count} sin poder
          evaluar
          {evidence === 'no-evidence'
            ? ' — el verde de esta pregunta sería por ausencia de prueba, no por buena salud'
            : ''}
        </span>
      )}

      {open && signals ? (
        <SignalTable signals={signals} catalog={catalog} thresholdsUsed={thresholdsUsed} />
      ) : null}
    </div>
  );
}

function StressCard({ run }: { run: AnalysisRun }) {
  const stress = run.verdict.stress;
  const scenarios = stress?.scenarios ?? [];

  return (
    <Card style={{ display: 'flex', flexDirection: 'column', gap: spacing.md }}>
      <CardTitle>Escenarios de stress</CardTitle>
      <InlineNotice>
        La cobertura de estos escenarios se mide sobre <strong>caja libre</strong> (flujo de
        explotación − inversión), no sobre el FFO. En una socimi puede no coincidir con la
        cobertura de la pestaña Dividendo, que sí usa FFO.
      </InlineNotice>

      {stress?.not_computable_reason ? (
        <InlineNotice>
          Faltan escenarios: {stress.not_computable_reason}.
        </InlineNotice>
      ) : null}

      {scenarios.length === 0 ? (
        <p style={{ margin: 0, color: colors.textMuted, fontSize: fontSize.sm }}>
          No se ha podido calcular ningún escenario para este valor.
        </p>
      ) : (
        <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'grid', gap: spacing.sm }}>
          {scenarios.map((scenario) => (
            <li
              key={scenario.key}
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: 2,
                paddingBottom: spacing.sm,
                borderBottom: `1px solid ${colors.border}`,
              }}
            >
              <span style={{ color: colors.textSubtle, fontSize: fontSize.xs }}>
                [{scenario.label}] {scenario.parameter}
              </span>
              <span style={{ color: colors.text, fontSize: fontSize.sm, lineHeight: 1.5 }}>
                {scenario.sentence}
              </span>
            </li>
          ))}
        </ul>
      )}

      {stress?.breakeven_fcf_drop ? (
        <p style={{ margin: 0, color: colors.textMuted, fontSize: fontSize.sm }}>
          Margen de caída de la caja libre antes de dejar de cubrir el dividendo:{' '}
          <strong style={{ color: colors.text }}>
            {(Number(stress.breakeven_fcf_drop) * 100).toLocaleString('es-ES', {
              maximumFractionDigits: 0,
            })}{' '}
            %
          </strong>
          .
        </p>
      ) : null}
    </Card>
  );
}

// ── Confianza y datos ─────────────────────────────────────────────────

function ConfidenceSection({
  run,
  statements,
  items,
}: {
  run: AnalysisRun;
  statements: FinancialStatement[] | undefined;
  items: CanonicalItemDefinition[] | undefined;
}) {
  const dc = run.data_completeness;
  const pct = (value: string) => Math.round(Number(value) * 100);
  const labelOf = (key: string) => items?.find((i) => i.key === key)?.label ?? key;

  const statementYears = (statements ?? []).map((s) => s.fiscal_year);
  const mismatch =
    statementYears.length > 0 &&
    statementYears.join(',') !== [...run.years_covered].sort((a, b) => a - b).join(',');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.lg }}>
      <Card style={{ display: 'flex', flexDirection: 'column', gap: spacing.md }}>
        <CardTitle>Cómo se calcula la confianza</CardTitle>
        <p style={{ margin: 0, color: colors.textMuted, fontSize: fontSize.sm, lineHeight: 1.6 }}>
          <strong style={{ color: colors.text }}>{pct(dc.value)} %</strong> = completitud{' '}
          {pct(dc.completeness_core)} % × frescura {Number(dc.staleness_factor).toLocaleString(
            'es-ES',
            { minimumFractionDigits: 1, maximumFractionDigits: 1 },
          )}
          .
        </p>
        <ul
          style={{
            margin: 0,
            paddingLeft: spacing.lg,
            color: colors.textMuted,
            fontSize: fontSize.sm,
            lineHeight: 1.6,
          }}
        >
          <li>
            <strong>Completitud</strong>: fracción de las 10 partidas núcleo publicadas por el
            filing en cada ejercicio. Una partida imputada a cero no cuenta como publicada
            {dc.imputed_core_count > 0
              ? ` — aquí hay ${dc.imputed_core_count} imputadas.`
              : '.'}
          </li>
          <li>
            <strong>Frescura</strong>: 1,0 si el último cierre tiene menos de 9 meses; 0,7 hasta
            18 meses; 0,4 a partir de ahí.
            {dc.days_stale !== null
              ? ` El último cierre (${dc.latest_fiscal_year_end ?? '—'}) tiene ${dc.days_stale} días.`
              : ''}
          </li>
        </ul>
        <InlineNotice>
          Para datos anuales, una confianza alta con un cierre de hace meses es normal: el último
          10-K es lo más reciente que existe.
        </InlineNotice>
      </Card>

      <Card style={{ display: 'flex', flexDirection: 'column', gap: spacing.md }}>
        <CardTitle>Partidas núcleo por ejercicio</CardTitle>
        <p style={{ margin: 0, color: colors.textMuted, fontSize: fontSize.xs, lineHeight: 1.5 }}>
          Sale de los estados financieros ingeridos, no del análisis. Un hueco aquí puede ser
          estructural y no reparable: un balance no clasificado (bancos, muchas socimis) no
          publica activo ni pasivo corriente, y una empresa que no reparte no «omite» el
          dividendo — vale cero.
        </p>
        {mismatch ? (
          <InlineNotice>
            Ojo: los estados en pantalla cubren {statementYears.join(', ')} y el análisis juzgó{' '}
            {run.years_covered.join(', ')}. Se ha reingerido después de analizar; vuelve a
            ejecutar el análisis para que coincidan.
          </InlineNotice>
        ) : null}
        {statements && statements.length > 0 ? (
          <div style={{ overflowX: 'auto' }}>
            <table
              style={{ width: '100%', borderCollapse: 'collapse', fontSize: fontSize.xs }}
            >
              <thead>
                <tr>
                  <th style={{ textAlign: 'left', padding: spacing.xs, color: colors.textMuted }}>
                    Partida
                  </th>
                  {statements.map((s) => (
                    <th
                      key={s.fiscal_year}
                      style={{ textAlign: 'right', padding: spacing.xs, color: colors.textMuted }}
                    >
                      {s.fiscal_year}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {CORE_ITEMS.map((key) => (
                  <tr key={key}>
                    <th
                      scope="row"
                      style={{
                        textAlign: 'left',
                        padding: spacing.xs,
                        color: colors.textMuted,
                        fontWeight: fontWeight.regular,
                        borderBottom: `1px solid ${colors.border}`,
                      }}
                    >
                      {labelOf(key)}
                    </th>
                    {statements.map((statement) => {
                      const present = statement[key] !== null;
                      return (
                        <td
                          key={`${key}-${statement.fiscal_year}`}
                          style={{
                            textAlign: 'right',
                            padding: spacing.xs,
                            borderBottom: `1px solid ${colors.border}`,
                            color: present ? colors.success : colors.textSubtle,
                          }}
                          title={present ? 'publicada' : 'ausente en el filing'}
                        >
                          {present ? '✓' : '—'}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <DegradedPanel
            title="Sin estados financieros cargados"
            reason="No se han podido leer los estados de este valor para cruzarlos con el análisis."
          />
        )}
      </Card>
    </div>
  );
}
