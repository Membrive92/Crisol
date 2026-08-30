'use client';

import { useState } from 'react';
import Link from 'next/link';

import {
  colors,
  EVIDENCE_LABEL,
  evidenceBreakdown,
  fontSize,
  fontWeight,
  questionEvidence,
  radius,
  coreItemCoverage,
  REPORT_SCOPE,
  reportSignalsOf,
  SAFETY,
  blockingSummary,
  dictamenLists,
  DICTAMEN_TITLES,
  overflowLabel,
  type DictamenRow,
  spacing,
  STRESS_ANCHOR,
  verdictWhyRows,
  WHY_ANCHOR,
  type WhySection,
  layout,
} from '@crisol/ui';
import type {
  AnalysisRun,
  CanonicalItemDefinition,
  FinancialStatement,
  QuestionSignal,
  QuestionVerdict,
  ReportSignal,
} from '@crisol/types';

import { Card, CardTitle } from '@/components/ui/card';
import { Segmented } from '@/components/ui/segmented';

import { BandChip, bandColors } from './band-chip';
import { DegradedPanel, InlineNotice } from './degraded-panel';
import { FlagList } from './flag-list';
import { SignalTable } from './signal-table';
import { StressDumbbell } from './stress-dumbbell';
import type { CatalogIndex, ScoreHelpIndex } from '@crisol/ui';

// PHASE-44.24.E — `SAFETY` y las dos listas de reglas viven en `@crisol/ui`:
// estaban duplicadas aquí y en el hero, y copiarlas a móvil habría hecho cuatro
// copias de lo que decide `_safety_profile` en el motor.

// PHASE-44.24.E — `CORE_ITEMS` y la cobertura por ejercicio viven en
// `@crisol/ui`: móvil enseña lo mismo, y una copia por app haría que una dijera
// «9 de 10» y la otra «10 de 10» sobre el mismo análisis.

export interface TabVerdictProps {
  /**
   * La sección «Qué ha cambiado», ya montada por la página.
   *
   * Llega como nodo y no como datos porque necesita el hook de comparación, que
   * a su vez lee la URL: montarlo aquí dentro haría que los tests que renderizan
   * esta pestaña sin router se cayeran (PHASE-44.24.F).
   */
  history?: React.ReactNode;
  /**
   * Modo dictamen (PHASE-44.24.G): sin selector de secciones. Esconderlo con
   * CSS de impresión lo dejaba VIVO en pantalla —pulsarlo escribía un `sub`
   * que la página descartaba— y además salía en el papel.
   */
  printMode?: boolean | undefined;
  run: AnalysisRun;
  catalog: CatalogIndex;
  statements: FinancialStatement[] | undefined;
  items: CanonicalItemDefinition[] | undefined;
  /** Fichas de scores y banderas del motor (PHASE-44.24.A). */
  help?: ScoreHelpIndex | undefined;
  /** A dónde lleva cada señal. Lo compone la página (PHASE-44.24.C.4). */
  hrefFor?: ((signal: QuestionSignal) => string | null) | undefined;
  /**
   * A dónde lleva una CLAVE de señal — la de una condición del sello.
   *
   * Se compone en la página igual que `hrefFor`: estos componentes se montan
   * sin router en los tests, así que ninguno puede leer la URL.
   */
  hrefForKey?: ((key: string) => string | null) | undefined;
  sub: string;
  onSubChange: (key: string) => void;
}

export function TabVerdict({
  run,
  catalog,
  statements,
  items,
  help,
  hrefFor,
  hrefForKey,
  sub,
  onSubChange,
  history,
  printMode = false,
}: TabVerdictProps) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.lg }}>
      {printMode ? null : (
        <Segmented
          label="Secciones del veredicto"
          value={sub}
          onChange={onSubChange}
          options={[
            { key: 'dictamen', label: 'Dictamen' },
            { key: 'datos', label: 'Confianza y datos' },
            { key: 'historia', label: 'Qué ha cambiado' },
          ]}
        />
      )}
      {sub === 'datos' ? (
        <ConfidenceSection run={run} statements={statements} items={items} />
      ) : sub === 'historia' ? (
        // La comparación con un análisis anterior (PHASE-44.24.F). Vive bajo el
        // veredicto y no en su propia pestaña porque responde a la misma
        // pregunta —«¿es seguro?»— con el eje del tiempo.
        history
      ) : (
        <DictamenSection
          run={run}
          catalog={catalog}
          help={help}
          hrefFor={hrefFor}
          hrefForKey={hrefForKey}
          printMode={printMode}
        />
      )}
    </div>
  );
}

// ── Dictamen ──────────────────────────────────────────────────────────

function DictamenSection({
  run,
  catalog,
  help,
  hrefFor,
  hrefForKey,
  printMode = false,
}: {
  run: AnalysisRun;
  catalog: CatalogIndex;
  help?: ScoreHelpIndex | undefined;
  hrefFor?: ((signal: QuestionSignal) => string | null) | undefined;
  hrefForKey?: ((key: string) => string | null) | undefined;
  printMode?: boolean | undefined;
}) {
  // La auditoría del sello nace plegada: el Dictamen se LEE de arriba abajo y
  // la matriz de reglas lo sostiene desde detrás. En papel va siempre abierta
  // — un dictamen impreso sin sus reglas no es auditable.
  const [auditOpen, setAuditOpen] = useState(false);
  const profile = run.verdict.safety_profile;
  const safety = SAFETY[profile.label];
  // Las filas del porqué salen de `@crisol/ui`: móvil y el dictamen imprimible
  // pintan exactamente las mismas (PHASE-44.24.E / 44.25).
  const why = verdictWhyRows(profile, run.report?.why, run.thresholds_used, catalog);
  const { blocking, blockingLabel } = blockingSummary(profile);
  // Las listas del sumario: selección por regla determinista, en la capa
  // compartida — las pintan también móvil y el dictamen imprimible.
  const lists = dictamenLists(run, catalog);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.lg }}>
      {/* §1 — El dictamen. Las cuatro preguntas con su frase del SERVIDOR van
          primero: son la prosa que ya existía, enterrada bajo la matriz de
          reglas. El feedback que reordena esto, literal: «apuntes técnicos que
          hacen inviable su entendimiento de forma rápida» (PHASE-44.26). */}
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
          <CardTitle>{DICTAMEN_TITLES.verdictum}</CardTitle>
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
        {run.verdict.questions.map((question) => (
          <QuestionBlock
            key={question.key}
            question={question}
            catalog={catalog}
            thresholdsUsed={run.thresholds_used}
            report={reportSignalsOf(run.report, question.key)}
            profile={run.report?.threshold_profile.effective.replace(/_/g, ' ')}
            hrefFor={hrefFor}
            sentence={run.report?.questions.find((q) => q.key === question.key)?.sentence}
          />
        ))}
      </Card>

      {/* §2 — El dictamen, razonado (PHASE-44.26): qué preocupa, qué está
          bien y los escenarios de stress en UNA card — el usuario los pidió
          juntos: «para aprovechar el espacio… un informe en texto
          desarrollado». Las entradas en prosa las compone el SERVIDOR
          (narrative 1.2.0); el cliente pinta filas con número y enlace. */}
      <Card style={{ display: 'flex', flexDirection: 'column', gap: spacing.md }}>
        <CardTitle>{DICTAMEN_TITLES.reasoned}</CardTitle>

        {/* Las tres partes EN HORIZONTAL: es lo que hace que la card ancha
            sirva de algo. `auto-fit` colapsa las pistas vacías, así que con
            tres columnas hijas salen tres columnas repartidas a partes iguales
            en un monitor y UNA sola por debajo de ~1.300 px — sin media query,
            que aquí no hay (los estilos son inline). El mínimo de 420 px es lo
            que necesita una fila «etiqueta · valor · banda — distancia» para
            no partirse en cuatro líneas. */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 420px), 1fr))',
            gap: spacing.lg,
            alignItems: 'start',
          }}
        >
          <section style={columnStyle}>
            <SectionHead>{DICTAMEN_TITLES.concerns}</SectionHead>
            {lists.concernsIntro ? <Prose emphasis>{lists.concernsIntro}</Prose> : null}
            {lists.concerns.length > 0 ? (
              <ul style={concernListStyle}>
                {lists.concerns.map((row) => (
                  <li key={row.key}>
                    <SummaryRow row={row} hrefForKey={hrefForKey} printMode={printMode} />
                  </li>
                ))}
                {overflowLabel(lists.concernsOverflow) ? (
                  <li style={{ color: colors.textSubtle }}>
                    {overflowLabel(lists.concernsOverflow)} — todas en las tablas de cada pregunta.
                  </li>
                ) : null}
              </ul>
            ) : run.report?.next_checks?.length ? (
              // Sin filas propias (un run sin señales estructuradas): la frase del
              // servidor, que ya distingue «nada que vigilar» de «no se puede
              // decir» y nunca promete un verde sobre lo no auditado.
              <ul style={concernListStyle}>
                {run.report.next_checks.map((check) => (
                  <li key={check.key}>{check.text}</li>
                ))}
              </ul>
            ) : null}
            {run.flags.length > 0 ? (
              <span style={{ color: colors.textMuted, fontSize: fontSize.xs }}>
                Banderas encendidas: {run.flags.length}
              </span>
            ) : null}
            <FlagList
              flags={run.flags}
              emptyLabel="El motor no ha encendido ninguna bandera."
              help={help}
            />
          </section>

          <section style={columnStyle}>
            <SectionHead>{DICTAMEN_TITLES.strengths}</SectionHead>
            {lists.strengthsIntro ? <Prose emphasis>{lists.strengthsIntro}</Prose> : null}
            {lists.strengths.length > 0 ? (
              <ul style={concernListStyle}>
                {lists.strengths.map((row) => (
                  <li key={row.key}>
                    <SummaryRow row={row} hrefForKey={hrefForKey} printMode={printMode} />
                  </li>
                ))}
                {overflowLabel(lists.strengthsOverflow) ? (
                  <li style={{ color: colors.textSubtle }}>
                    {overflowLabel(lists.strengthsOverflow)} — el resto, en sus pestañas.
                  </li>
                ) : null}
              </ul>
            ) : (
              <Prose muted>Ninguna señal comprobada salió en verde en este análisis.</Prose>
            )}
            {lists.scenariosHolding.map((sentence) => (
              <Prose key={sentence} muted>
                {sentence}
              </Prose>
            ))}
            {lists.clean.length > 0 ? (
              <p
                style={{
                  margin: 0,
                  maxWidth: layout.prose,
                  color: colors.textMuted,
                  fontSize: fontSize.xs,
                  lineHeight: 1.6,
                }}
              >
                {/* La razón es la PERSISTIDA por señal, no una oración compuesta
                aquí: el cliente no redacta afirmaciones de verificación. */}
                Comprobado y limpio: {lists.clean.map((check) => check.label).join(' · ')} —{' '}
                {lists.clean[0]?.reason}.
              </p>
            ) : null}
            {lists.discarded.length > 0 ? (
              <p
                style={{
                  margin: 0,
                  maxWidth: layout.prose,
                  color: colors.textMuted,
                  fontSize: fontSize.xs,
                  lineHeight: 1.6,
                }}
              >
                Comprobado y descartado del sello: {lists.discarded.join(' · ')}.
              </p>
            ) : null}
            <span style={{ color: colors.textSubtle, fontSize: fontSize.xs }}>
              {DICTAMEN_TITLES.strengthsFootnote}
            </span>
          </section>

          <section style={columnStyle}>
            <StressSection run={run} marginSentence={lists.stressMargin} />
          </section>
        </div>

        {/* El cierre va a ANCHO COMPLETO, fuera del grid: es la conclusión del
            informe, no una cuarta columna. */}
        {why.modelsDisagree ? <InlineNotice>{why.modelsDisagree}</InlineNotice> : null}
        {why.exitSentence ? <Prose>{why.exitSentence}</Prose> : null}
      </Card>

      {/* §5 — La auditoría del sello, PLEGADA por defecto: la matriz de reglas
          que produce el sello, condición a condición. En el dictamen impreso va
          siempre abierta y su control no se renderiza — un modo que ignora un
          control no lo esconde, no lo pinta (PHASE-44.24.H). */}
      <Card id={WHY_ANCHOR} style={{ display: 'flex', flexDirection: 'column', gap: spacing.md }}>
        {printMode ? (
          <CardTitle>{DICTAMEN_TITLES.audit}</CardTitle>
        ) : (
          <button
            type="button"
            aria-expanded={auditOpen}
            onClick={() => setAuditOpen((v) => !v)}
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: 2,
              background: 'none',
              border: 'none',
              padding: 0,
              cursor: 'pointer',
              textAlign: 'left',
            }}
          >
            <CardTitle>
              {auditOpen ? '▾' : '▸'} {DICTAMEN_TITLES.audit}
            </CardTitle>
            <span style={{ color: colors.textSubtle, fontSize: fontSize.xs }}>
              {DICTAMEN_TITLES.auditHint}
            </span>
          </button>
        )}

        {auditOpen || printMode ? (
          <>
            <p
              style={{
                margin: 0,
                maxWidth: layout.prose,
                color: colors.textMuted,
                fontSize: fontSize.sm,
                lineHeight: 1.5,
              }}
            >
              El perfil no es una nota media: sale de reglas fijas sobre los scores forenses y la
              bandera del dividendo. Estas son, con lo que ha pasado en este análisis. Es una
              comprobación de reglas, no una recomendación de compra o venta.
            </p>

            {why.sections.map((section) => (
              <RuleChecklist key={section.key} section={section} hrefForKey={hrefForKey} />
            ))}

            {why.legacy ? (
              <InlineNotice>
                Este análisis lo produjo un motor anterior, que no registraba la matriz condición a
                condición: de las de «Conservador» no quedó constancia. Vuelve a analizar para ver
                el detalle completo y qué haría falta para salir del perfil.
              </InlineNotice>
            ) : null}

            {blocking.length > 0 ? (
              <InlineNotice>
                <strong>{blockingLabel}</strong>
                {blocking.join('; ')}.
              </InlineNotice>
            ) : null}

            <InlineNotice>
              Regla del semáforo: <strong>rojo</strong> si hay ≥1 señal roja ·{' '}
              <strong>ámbar</strong> si hay ≥2 ámbar · <strong>verde</strong> en el resto. Una señal
              sin banda o no calculable no cuenta ni a favor ni en contra — por eso cada pregunta
              declara cuántas pudo evaluar.
            </InlineNotice>
          </>
        ) : null}
      </Card>

      <Card style={{ display: 'flex', flexDirection: 'column', gap: spacing.sm }}>
        <CardTitle size="sm">Alcance: lo que este informe NO cubre</CardTitle>
        <ul
          style={{
            margin: 0,
            maxWidth: layout.prose,
            paddingLeft: spacing.lg,
            color: colors.textMuted,
            fontSize: fontSize.sm,
            lineHeight: 1.6,
          }}
        >
          {/* El texto vive en `@crisol/ui` (PHASE-44.24.E): lo pintan también
              el veredicto de móvil y el dictamen imprimible, y una copia por
              sitio es cómo la versión impresa acaba prometiendo otro alcance. */}
          {REPORT_SCOPE.map((entry) => (
            <li key={entry.term}>
              <strong>{entry.term}.</strong> {entry.meaning}
            </li>
          ))}
        </ul>
      </Card>

      <p
        style={{
          margin: 0,
          maxWidth: layout.prose,
          color: colors.textSubtle,
          fontSize: fontSize.xs,
          lineHeight: 1.6,
        }}
      >
        Motor {run.engine_version} · umbrales {run.thresholds_version} · ejercicios{' '}
        {run.years_covered.join(', ')} · análisis del{' '}
        {new Date(run.run_date).toLocaleString('es-ES')}
      </p>
    </div>
  );
}

/** Un párrafo del informe. `emphasis` = entrada de sección del servidor. */
function Prose({
  children,
  muted = false,
  emphasis = false,
}: {
  children: React.ReactNode;
  muted?: boolean;
  emphasis?: boolean;
}) {
  return (
    <p
      style={{
        margin: 0,
        maxWidth: layout.prose,
        color: muted ? colors.textMuted : colors.text,
        fontSize: fontSize.sm,
        lineHeight: 1.6,
        fontWeight: emphasis ? fontWeight.semibold : fontWeight.regular,
      }}
    >
      {children}
    </p>
  );
}

/** La cabecera de una sección dentro de la card del dictamen razonado. */
function SectionHead({ children }: { children: React.ReactNode }) {
  return (
    <span
      style={{
        color: colors.textMuted,
        fontSize: fontSize.xs,
        fontWeight: fontWeight.semibold,
        textTransform: 'uppercase',
        letterSpacing: '0.04em',
        marginTop: spacing.xs,
      }}
    >
      {children}
    </span>
  );
}

/**
 * Una de las tres columnas del dictamen razonado.
 *
 * Sin `maxWidth: layout.prose`: el ancho de línea ya lo acota la propia
 * columna, y volver a acotarlo dentro dejaría media columna vacía — que es el
 * defecto que esta disposición viene a arreglar.
 */
const columnStyle: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: spacing.sm,
  minWidth: 0,
};

/** El estilo común de las listas del sumario. */
const concernListStyle: React.CSSProperties = {
  margin: 0,
  paddingLeft: spacing.lg,
  color: colors.text,
  fontSize: fontSize.sm,
  lineHeight: 1.7,
  display: 'flex',
  flexDirection: 'column',
  gap: 2,
  listStyle: 'disc',
};

/**
 * Una fila del sumario: etiqueta enlazada, valor, banda, distancia y — si la
 * señal no tiene número — las frases persistidas que le dan cuerpo.
 */
function SummaryRow({
  row,
  hrefForKey,
  printMode,
}: {
  row: DictamenRow;
  hrefForKey?: ((key: string) => string | null) | undefined;
  printMode: boolean;
}) {
  const href = printMode ? null : (hrefForKey?.(row.key) ?? null);
  return (
    <span style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
      <span>
        {href ? (
          <Link href={href as never} style={{ color: colors.primary }}>
            {row.label}
          </Link>
        ) : (
          row.label
        )}
        {row.value ? ` · ${row.value}` : ''} <BandChip band={row.band} />
        {row.distance ? <span style={{ color: colors.textMuted }}> — {row.distance}</span> : null}
        {row.unaudited ? (
          <span style={{ color: colors.textSubtle, fontSize: fontSize.xs }}>
            {' '}
            · {EVIDENCE_LABEL['not-audited'].toLowerCase()}
          </span>
        ) : null}
      </span>
      {row.sentences.map((sentence) => (
        <span
          key={sentence}
          style={{ color: colors.textMuted, fontSize: fontSize.xs, lineHeight: 1.5 }}
        >
          {sentence}
        </span>
      ))}
    </span>
  );
}

/** ¿El motivo bloqueante es la negación de esta regla? El motor los escribe en
 *  negativo («M-Score no está en verde») y la regla está en positivo. */
/**
 * Una lista de condiciones del sello, con su estado en PALABRAS.
 *
 * El glifo anterior era bimodal: en la lista de «Evitar», cumplir una condición
 * pintaba ✕ —que junto a una proposición se lee como «no es verdad»— y no
 * cumplirla pintaba ✓ verde sobre una catástrofe. La única línea que respondía
 * a «por qué evitar» salía literalmente negada (PHASE-44.25).
 */
function RuleChecklist({
  section,
  hrefForKey,
}: {
  section: WhySection;
  hrefForKey?: ((key: string) => string | null) | undefined;
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
        {section.title}
      </span>
      <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'grid', gap: spacing.xs }}>
        {section.rows.map((row) => (
          <li
            key={row.key}
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: 2,
              fontSize: fontSize.sm,
              color: row.isBad ? colors.danger : colors.textMuted,
            }}
          >
            <span style={{ display: 'flex', gap: spacing.sm, flexWrap: 'wrap' }}>
              <span
                style={{
                  color: row.isBad ? colors.danger : colors.textSubtle,
                  fontWeight: fontWeight.semibold,
                  fontSize: fontSize.xs,
                  textTransform: 'uppercase',
                  letterSpacing: '0.03em',
                  whiteSpace: 'nowrap',
                }}
              >
                {row.stateLabel}
              </span>
              <span style={{ color: row.isBad ? colors.danger : colors.textMuted }}>
                {row.text}
              </span>
              {row.decided ? (
                <span
                  style={{
                    color: colors.danger,
                    backgroundColor: colors.dangerSoft,
                    borderRadius: radius.sm,
                    padding: `0 ${spacing.xs}px`,
                    fontSize: fontSize.xs,
                    fontWeight: fontWeight.semibold,
                    whiteSpace: 'nowrap',
                  }}
                >
                  decidió el veredicto
                </span>
              ) : null}
            </span>
            {row.reason ? (
              <span style={{ color: colors.textSubtle, fontSize: fontSize.xs }}>{row.reason}</span>
            ) : null}
            {row.signals.map((signal) => {
              const href = hrefForKey?.(signal.key) ?? null;
              const texto = [signal.label, signal.reading, signal.cut].filter(Boolean).join(' · ');
              return (
                <span key={signal.key} style={{ color: colors.textSubtle, fontSize: fontSize.xs }}>
                  {/* Sin destino real no hay enlace: se pinta como texto
                      (PHASE-44.24.H). */}
                  {href ? (
                    <Link href={href as never} style={{ color: colors.primary }}>
                      {texto}
                    </Link>
                  ) : (
                    texto
                  )}
                </span>
              );
            })}
          </li>
        ))}
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
        Este análisis lo produjo un motor anterior, que no registraba qué señales se evaluaron. El
        veredicto de abajo <strong>no es auditable</strong>: vuelve a ejecutar el análisis para ver
        el desglose.
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
  report,
  profile,
  hrefFor,
  sentence,
}: {
  question: QuestionVerdict;
  catalog: CatalogIndex;
  thresholdsUsed: AnalysisRun['thresholds_used'];
  report?: Map<string, ReportSignal> | undefined;
  profile?: string | undefined;
  hrefFor?: ((signal: QuestionSignal) => string | null) | undefined;
  sentence?: string | undefined;
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
      label={EVIDENCE_LABEL[evidence] || undefined}
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

      {/* La frase la compone el SERVIDOR (PHASE-44.24.B): determinista, con
          plantillas versionadas y goldens. Aquí no se redacta nada, para que la
          pantalla y el dictamen impreso no puedan decir cosas distintas. */}
      {sentence ? (
        <p
          style={{
            margin: 0,
            maxWidth: layout.prose,
            color: colors.text,
            fontSize: fontSize.sm,
            lineHeight: 1.5,
          }}
        >
          {sentence}
        </p>
      ) : null}

      {evidence === 'not-recorded' ? (
        <LegacySignals question={question} catalog={catalog} />
      ) : (
        <span style={{ color: colors.textMuted, fontSize: fontSize.xs }}>
          {evidenceBreakdown(question)}
          {evidence === 'no-evidence'
            ? ' — el verde de esta pregunta sería por ausencia de prueba, no por buena salud'
            : ''}
        </span>
      )}

      {/* El cuarto estado (PHASE-44.21): falta un PORTANTE, así que el veredicto
          no se sostiene aunque el resto de señales estén verdes. Se dice QUÉ
          falta, porque «no auditada» a secas no es accionable. */}
      {evidence === 'not-audited' && question.unaudited_reasons?.length ? (
        <ul
          style={{
            margin: 0,
            maxWidth: layout.prose,
            paddingLeft: spacing.lg,
            color: colors.textMuted,
            fontSize: fontSize.xs,
          }}
        >
          {question.unaudited_reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      ) : null}

      {question.notes?.map((note) => (
        <span key={note} style={{ color: colors.textSubtle, fontSize: fontSize.xs }}>
          {note}
        </span>
      ))}

      {open && signals ? (
        <SignalTable
          signals={signals}
          catalog={catalog}
          thresholdsUsed={thresholdsUsed}
          report={report}
          profile={profile}
          hrefFor={hrefFor}
        />
      ) : null}
    </div>
  );
}

function StressSection({
  run,
  marginSentence,
}: {
  run: AnalysisRun;
  /** El margen enunciado por el SERVIDOR. Con él, el párrafo local calla. */
  marginSentence?: string | null | undefined;
}) {
  const stress = run.verdict.stress;
  const scenarios = stress?.scenarios ?? [];

  return (
    // El `id` es el destino de la señal «Escenario de stress» del veredicto
    // (`STRESS_ANCHOR`). Desde PHASE-44.26 vive DENTRO de la card del dictamen
    // razonado — el usuario pidió el stress junto a lo bueno y lo malo, no en
    // su propia isla. `scrollMarginTop` deja sitio a la cabecera fija.
    <div
      id={STRESS_ANCHOR}
      style={{ display: 'flex', flexDirection: 'column', gap: spacing.md, scrollMarginTop: 120 }}
    >
      <CardTitle size="sm">Escenarios de stress</CardTitle>
      <InlineNotice>
        La cobertura de estos escenarios se mide sobre <strong>caja libre</strong> (flujo de
        explotación − inversión), no sobre el FFO. En una socimi puede no coincidir con la cobertura
        de la pestaña Dividendo, que sí usa FFO.
      </InlineNotice>

      {stress?.not_computable_reason ? (
        <InlineNotice>Faltan escenarios: {stress.not_computable_reason}.</InlineNotice>
      ) : null}

      {scenarios.length === 0 ? (
        <p
          style={{
            margin: 0,
            maxWidth: layout.prose,
            color: colors.textMuted,
            fontSize: fontSize.sm,
          }}
        >
          No se ha podido calcular ningún escenario para este valor.
        </p>
      ) : (
        <>
          {/* El dibujo primero y las frases debajo: el dumbbell contesta «¿cuánto
            se mueve y sigue cubriendo?» de un vistazo, y la frase del motor
            explica el escenario. Ninguno sustituye al otro. */}
          <StressDumbbell scenarios={scenarios} />
          <ul
            style={{ margin: 0, padding: 0, listStyle: 'none', display: 'grid', gap: spacing.sm }}
          >
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
        </>
      )}

      {marginSentence ? (
        // La frase del SERVIDOR (narrative 1.2.0), con goldens. El cálculo
        // local de abajo queda solo para backends que aún no la mandan.
        <p
          style={{
            margin: 0,
            maxWidth: layout.prose,
            color: colors.textMuted,
            fontSize: fontSize.sm,
          }}
        >
          {marginSentence}
        </p>
      ) : stress?.breakeven_fcf_drop ? (
        <p
          style={{
            margin: 0,
            maxWidth: layout.prose,
            color: colors.textMuted,
            fontSize: fontSize.sm,
          }}
        >
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
    </div>
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
  const coverage = coreItemCoverage(statements, items, run.years_covered);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.lg }}>
      <Card style={{ display: 'flex', flexDirection: 'column', gap: spacing.md }}>
        <CardTitle>Cómo se calcula la confianza</CardTitle>
        <p
          style={{
            margin: 0,
            maxWidth: layout.prose,
            color: colors.textMuted,
            fontSize: fontSize.sm,
            lineHeight: 1.6,
          }}
        >
          <strong style={{ color: colors.text }}>{pct(dc.value)} %</strong> = completitud{' '}
          {pct(dc.completeness_core)} % × frescura{' '}
          {Number(dc.staleness_factor).toLocaleString('es-ES', {
            minimumFractionDigits: 1,
            maximumFractionDigits: 1,
          })}
          .
        </p>
        <ul
          style={{
            margin: 0,
            maxWidth: layout.prose,
            paddingLeft: spacing.lg,
            color: colors.textMuted,
            fontSize: fontSize.sm,
            lineHeight: 1.6,
          }}
        >
          <li>
            <strong>Completitud</strong>: fracción de las 10 partidas núcleo publicadas por el
            filing en cada ejercicio. Una partida imputada a cero no cuenta como publicada
            {dc.imputed_core_count > 0 ? ` — aquí hay ${dc.imputed_core_count} imputadas.` : '.'}
          </li>
          <li>
            <strong>Frescura</strong>: 1,0 si el último cierre tiene menos de 9 meses; 0,7 hasta 18
            meses; 0,4 a partir de ahí.
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
        <p
          style={{
            margin: 0,
            maxWidth: layout.prose,
            color: colors.textMuted,
            fontSize: fontSize.xs,
            lineHeight: 1.5,
          }}
        >
          Sale de los estados financieros ingeridos, no del análisis. Un hueco aquí puede ser
          estructural y no reparable: un balance no clasificado (bancos, muchas socimis) no publica
          activo ni pasivo corriente, y una empresa que no reparte no «omite» el dividendo — vale
          cero.
        </p>
        {coverage.mismatch ? (
          <InlineNotice>
            Ojo: los estados en pantalla cubren {coverage.years.join(', ')} y el análisis juzgó{' '}
            {run.years_covered.join(', ')}. Se ha reingerido después de analizar; vuelve a ejecutar
            el análisis para que coincidan.
          </InlineNotice>
        ) : null}
        {statements && statements.length > 0 ? (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: fontSize.xs }}>
              <thead>
                <tr>
                  <th style={{ textAlign: 'left', padding: spacing.xs, color: colors.textMuted }}>
                    Partida
                  </th>
                  {coverage.years.map((year) => (
                    <th
                      key={year}
                      style={{ textAlign: 'right', padding: spacing.xs, color: colors.textMuted }}
                    >
                      {year}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {coverage.rows.map((row) => (
                  <tr key={row.key}>
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
                      {row.label}
                    </th>
                    {row.present.map((present, index) => (
                      <td
                        key={`${row.key}-${coverage.years[index]}`}
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
                    ))}
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
