'use client';

import { useEffect, useMemo, useState } from 'react';

import type { Category, ImportPreviewResponse, ImportSource } from '@crisol/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';

import { Button } from '../ui/button';
import { Spinner } from '../ui/spinner';
import { CategoryCombobox } from '../transactions/category-combobox';
import { looksLikeFinancedOperation } from '../transfers/convert-to-debt-dialog';

const SOURCE_LABEL: Record<ImportSource, string> = {
  pdfplumber_smart: 'PDF — tabla de transacciones detectada automáticamente',
  pdfplumber_legacy: 'PDF — modo manual (mapeo de columnas)',
  vision: 'PDF — procesado por IA local (visión)',
  csv: 'CSV',
  xlsx: 'Excel (XLSX) — modo manual',
  xlsx_smart: 'Excel (XLSX) — columnas detectadas automáticamente',
};

const SOURCE_HELP: Record<ImportSource, string> = {
  pdfplumber_smart:
    'La heurística identificó la tabla de movimientos y descartó las tablas de resumen. Tu mapeo manual se ignoró porque ya no hace falta.',
  pdfplumber_legacy:
    'No pudimos identificar una tabla de transacciones clara. Usamos las columnas que indicaste en el paso anterior.',
  vision:
    'Procesamos el PDF como imágenes con el modelo local. Las filas pueden tener pequeñas variaciones respecto al texto original.',
  csv: 'Aplicamos el mapeo del paso anterior. Cada fila viene del fichero tal cual.',
  xlsx: 'Aplicamos el mapeo del paso anterior. Cada fila viene de la primera hoja del libro.',
  xlsx_smart:
    'Detectamos automáticamente las columnas de fecha, importe y concepto. Tu mapeo manual se ignoró porque ya no hace falta.',
};

export interface PreviewStepProps {
  preview: ImportPreviewResponse;
  /** Si está cargando el commit final. */
  committing: boolean;
  /** Si está cargando una re-extracción con IA. */
  reprocessing: boolean;
  /**
   * Cuándo mostrar el botón "Procesar con IA". Solo tiene sentido para
   * PDFs cuando todavía no se ha intentado visión.
   */
  canRetryWithVision: boolean;
  /** Categorías del usuario para los dropdowns de mapeo por concepto. */
  categories: Category[];
  errorMessage: string | null;
  /**
   * El caller recibe el mapping `concepto banco → category_id` que el
   * usuario asignó. Se manda al endpoint de commit para autoasignar
   * categorías y guardar las equivalencias.
   */
  onConfirm: (categoryOverrides: Record<string, string>) => void;
  onRetryWithVision: () => void;
  onBack: () => void;
  /**
   * Lanza una sugerencia con IA local para los conceptos sin
   * sugerencia previa. Devuelve `{concept_norm: category_id | null}`
   * o `undefined` si la llamada falla.
   */
  onAiSuggest?: () => Promise<Record<string, string | null> | undefined>;
  aiSuggesting?: boolean;
}

const MAX_VISIBLE_ROWS = 50;
const UNASSIGNED = '';

export function PreviewStep({
  preview,
  committing,
  reprocessing,
  canRetryWithVision,
  categories,
  errorMessage,
  onConfirm,
  onRetryWithVision,
  onBack,
  onAiSuggest,
  aiSuggesting = false,
}: PreviewStepProps) {
  const visibleRows = preview.rows.slice(0, MAX_VISIBLE_ROWS);
  const hiddenCount = Math.max(0, preview.total_rows - visibleRows.length);

  // Estado del mapping concepto → category_id que el usuario va asignando.
  // Inicializa con las sugerencias del backend (equivalencias guardadas).
  const initialMapping = useMemo<Record<string, string>>(() => {
    const out: Record<string, string> = {};
    for (const g of preview.bank_concept_groups) {
      out[g.concept] = g.suggested_category_id ?? UNASSIGNED;
    }
    return out;
  }, [preview.bank_concept_groups]);
  const [conceptMapping, setConceptMapping] =
    useState<Record<string, string>>(initialMapping);

  // Si cambia el preview (p.ej. tras "procesar con IA"), reinicializamos
  // el estado al nuevo set de grupos.
  useEffect(() => {
    setConceptMapping(initialMapping);
  }, [initialMapping]);

  function handleConfirmClick() {
    // Filtra las entradas vacías — no se mandan al backend.
    const overrides: Record<string, string> = {};
    for (const [concept, catId] of Object.entries(conceptMapping)) {
      if (catId) overrides[concept] = catId;
    }
    onConfirm(overrides);
  }

  return (
    <div>
      <header style={{ marginBottom: spacing.md }}>
        <div style={{ fontSize: fontSize.sm, color: colors.textMuted }}>
          Fuente
        </div>
        <div
          style={{
            fontSize: fontSize.md,
            fontWeight: fontWeight.semibold,
            color: colors.text,
          }}
        >
          {SOURCE_LABEL[preview.source]}
        </div>
        <p
          style={{
            margin: `${spacing.xs}px 0 0 0`,
            fontSize: fontSize.sm,
            color: colors.textMuted,
            lineHeight: 1.4,
          }}
        >
          {SOURCE_HELP[preview.source]}
        </p>
      </header>

      {preview.bank_concept_groups.length > 0 ? (
        <BankConceptMappingSection
          groups={preview.bank_concept_groups}
          categories={categories}
          mapping={conceptMapping}
          onChange={setConceptMapping}
          onAiSuggest={
            onAiSuggest
              ? async () => {
                  const suggestions = await onAiSuggest();
                  if (!suggestions) return;
                  // Aplicar las sugerencias IA al estado: para cada
                  // concept en el grupo, si su forma normalizada está
                  // en suggestions y el dropdown actual está vacío,
                  // la asignamos.
                  setConceptMapping((prev) => {
                    const next = { ...prev };
                    for (const g of preview.bank_concept_groups) {
                      const norm = g.concept.trim().toLowerCase();
                      if (next[g.concept]) continue; // no pisar lo asignado
                      const sug = suggestions[norm];
                      if (sug) next[g.concept] = sug;
                    }
                    return next;
                  });
                }
              : undefined
          }
          aiSuggesting={aiSuggesting}
        />
      ) : null}

      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: spacing.sm,
        }}
      >
        <span style={{ fontSize: fontSize.sm, color: colors.text }}>
          <strong>{preview.total_rows}</strong>{' '}
          {preview.total_rows === 1 ? 'fila detectada' : 'filas detectadas'}
        </span>
        {hiddenCount > 0 ? (
          <span style={{ fontSize: fontSize.xs, color: colors.textMuted }}>
            Mostrando las primeras {MAX_VISIBLE_ROWS} · {hiddenCount} más al confirmar
          </span>
        ) : null}
      </div>

      <div
        style={{
          border: `1px solid ${colors.border}`,
          borderRadius: radius.sm,
          overflow: 'hidden',
          marginBottom: spacing.md,
          maxHeight: 400,
          overflowY: 'auto',
        }}
      >
        <table
          style={{
            width: '100%',
            borderCollapse: 'collapse',
            fontSize: fontSize.sm,
          }}
        >
          <thead
            style={{
              position: 'sticky',
              top: 0,
              backgroundColor: colors.surfaceMuted,
            }}
          >
            <tr>
              <th style={thStyle}>Fecha</th>
              <th style={thStyle}>Descripción</th>
              <th style={thStyle}>Categoría (banco)</th>
              <th style={{ ...thStyle, textAlign: 'right' }}>Importe</th>
              <th style={{ ...thStyle, textAlign: 'right' }}>Saldo</th>
            </tr>
          </thead>
          <tbody>
            {visibleRows.map((row, idx) => (
              <tr
                key={idx}
                style={{
                  borderTop: idx === 0 ? 'none' : `1px solid ${colors.border}`,
                }}
              >
                <td style={tdStyle}>{row.occurred_at || '—'}</td>
                <td style={tdStyle}>
                  {row.description || '—'}
                  {looksLikeFinancedOperation(row.description ?? null) ? (
                    <span
                      style={{
                        marginLeft: spacing.xs,
                        padding: `2px ${spacing.xs}px`,
                        borderRadius: radius.sm,
                        fontSize: 10,
                        fontWeight: fontWeight.semibold,
                        textTransform: 'uppercase',
                        letterSpacing: '0.04em',
                        backgroundColor: colors.warningSoft,
                        color: colors.warning,
                        border: `1px solid ${colors.warning}`,
                      }}
                      title="Tras importar, ve al detalle de esta tx para registrarla como deuda."
                    >
                      Posible deuda
                    </span>
                  ) : null}
                </td>
                <td
                  style={{ ...tdStyle, color: colors.textMuted, fontSize: fontSize.xs }}
                >
                  {row.category_name || '—'}
                </td>
                <td style={{ ...tdStyle, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                  {row.amount || '—'}
                </td>
                <td
                  style={{
                    ...tdStyle,
                    textAlign: 'right',
                    fontVariantNumeric: 'tabular-nums',
                    color: colors.textMuted,
                  }}
                >
                  {row.statement_balance ?? '—'}
                </td>
              </tr>
            ))}
            {visibleRows.length === 0 ? (
              <tr>
                <td
                  colSpan={5}
                  style={{
                    ...tdStyle,
                    textAlign: 'center',
                    color: colors.textMuted,
                    padding: spacing.lg,
                  }}
                >
                  No se detectaron filas. Vuelve atrás y revisa el mapeo o
                  prueba con IA.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>

      {errorMessage ? (
        <div
          style={{
            color: colors.danger,
            fontSize: fontSize.sm,
            marginBottom: spacing.sm,
          }}
        >
          {errorMessage}
        </div>
      ) : null}

      <div
        style={{
          display: 'flex',
          gap: spacing.sm,
          marginTop: spacing.md,
          flexWrap: 'wrap',
          alignItems: 'center',
        }}
      >
        <Button
          type="button"
          variant="ghost"
          onClick={onBack}
          disabled={committing || reprocessing}
        >
          ← Atrás
        </Button>
        {canRetryWithVision ? (
          <Button
            type="button"
            variant="secondary"
            onClick={onRetryWithVision}
            disabled={committing || reprocessing}
          >
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
              {reprocessing ? <Spinner size={14} color={colors.primary} /> : null}
              {reprocessing ? 'Procesando con IA…' : 'Procesar con IA'}
            </span>
          </Button>
        ) : null}
        <Button
          type="button"
          onClick={handleConfirmClick}
          disabled={committing || reprocessing || preview.total_rows === 0}
        >
          {committing
            ? 'Importando…'
            : `Importar ${preview.total_rows} ${
                preview.total_rows === 1 ? 'fila' : 'filas'
              }`}
        </Button>
      </div>
    </div>
  );
}

const thStyle = {
  padding: `${spacing.xs}px ${spacing.sm}px`,
  textAlign: 'left' as const,
  fontSize: fontSize.xs,
  fontWeight: fontWeight.semibold,
  color: colors.textMuted,
  textTransform: 'uppercase' as const,
  letterSpacing: 0.5,
  borderBottom: `1px solid ${colors.border}`,
};

const tdStyle = {
  padding: `${spacing.xs}px ${spacing.sm}px`,
  color: colors.text,
  verticalAlign: 'top' as const,
};


interface BankConceptMappingSectionProps {
  groups: ImportPreviewResponse['bank_concept_groups'];
  categories: Category[];
  mapping: Record<string, string>;
  onChange: (next: Record<string, string>) => void;
  onAiSuggest?: (() => Promise<void> | void) | undefined;
  aiSuggesting?: boolean;
}

function sourceLabelFor(source: string | null): string {
  if (source === 'saved_mapping') return 'sugerencia guardada';
  if (source === 'rule') return 'sugerencia por regla';
  if (source === 'ai') return 'sugerencia IA';
  return '';
}

function BankConceptMappingSection({
  groups,
  categories,
  mapping,
  onChange,
  onAiSuggest,
  aiSuggesting = false,
}: BankConceptMappingSectionProps) {
  // Cuenta como "resuelto" cualquier grupo que (a) tiene categoría
  // asignada en el dropdown, (b) tiene reglas mixtas que se aplicarán
  // fila a fila al confirmar.
  const resolvedCount = groups.filter(
    (g) => g.has_mixed_rule_matches || Boolean(mapping[g.concept]),
  ).length;
  const remaining = groups.length - resolvedCount;

  return (
    <section
      style={{
        backgroundColor: colors.surfaceMuted,
        border: `1px solid ${colors.border}`,
        borderRadius: radius.md,
        padding: spacing.md,
        marginBottom: spacing.md,
      }}
    >
      <header
        style={{
          marginBottom: spacing.sm,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          gap: spacing.sm,
        }}
      >
        <div style={{ flex: 1, minWidth: 0 }}>
          <div
            style={{
              fontSize: fontSize.sm,
              fontWeight: fontWeight.semibold,
              color: colors.text,
            }}
          >
            Conceptos del banco ({resolvedCount}/{groups.length} resueltos)
          </div>
          <p
            style={{
              margin: `${spacing.xs}px 0 0 0`,
              fontSize: fontSize.xs,
              color: colors.textMuted,
              lineHeight: 1.4,
            }}
          >
            Cada concepto puede tener una categoría asignada. Si la dejas
            sugerida (resaltado azul) o vacía, los cambios se persisten al
            confirmar.
            {remaining > 0
              ? ` ${remaining} ${remaining === 1 ? 'concepto' : 'conceptos'} sin sugerencia: se importarán sin categoría a menos que asignes una.`
              : ''}
          </p>
        </div>
        {onAiSuggest && remaining > 0 ? (
          <Button
            type="button"
            variant="secondary"
            onClick={() => {
              void onAiSuggest();
            }}
            disabled={aiSuggesting}
          >
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
              {aiSuggesting ? <Spinner size={14} color={colors.primary} /> : null}
              {aiSuggesting ? 'Pensando…' : 'Sugerir con IA'}
            </span>
          </Button>
        ) : null}
      </header>

      <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.xs }}>
        {groups.map((g) => {
          const value = mapping[g.concept] ?? '';
          const isSuggestion =
            g.suggested_category_id !== null &&
            value === g.suggested_category_id;
          const sourceLabel = isSuggestion
            ? sourceLabelFor(g.suggestion_source)
            : null;
          return (
            <div
              key={g.concept}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: spacing.sm,
              }}
            >
              <div style={{ flex: 1, minWidth: 0 }}>
                <div
                  style={{
                    fontSize: fontSize.sm,
                    color: colors.text,
                    fontWeight: fontWeight.medium,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                  title={g.concept}
                >
                  {g.concept}
                </div>
                <div style={{ fontSize: fontSize.xs, color: colors.textMuted }}>
                  {g.count} {g.count === 1 ? 'fila' : 'filas'}
                  {sourceLabel ? ` · ${sourceLabel}` : ''}
                  {g.has_mixed_rule_matches
                    ? ' · reglas mixtas (se aplicarán fila a fila)'
                    : ''}
                </div>
              </div>
              {g.has_mixed_rule_matches ? (
                <span
                  style={{
                    width: 220,
                    fontSize: fontSize.xs,
                    color: colors.textMuted,
                    fontStyle: 'italic',
                  }}
                >
                  Categoría por fila al confirmar
                </span>
              ) : (
                // Mismo selector agrupado (Ingresos/Gastos/Transferencias)
                // que en el alta manual, para que elegir una categoría de
                // transferencia se lea como "movimiento entre cuentas" y no
                // como un gasto. `highlight` conserva el aviso de sugerencia
                // del backend; el concepto es el label accesible (oculto).
                <div style={{ width: 220 }}>
                  <CategoryCombobox
                    label={`Categoría para ${g.concept}`}
                    hideLabel
                    dense
                    highlight={isSuggestion}
                    categories={categories}
                    value={value}
                    onChange={(catId) =>
                      onChange({ ...mapping, [g.concept]: catId })
                    }
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
