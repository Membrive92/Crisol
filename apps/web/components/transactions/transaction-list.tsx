'use client';

import { useMemo } from 'react';
import { useRouter } from 'next/navigation';

import { useCurrencyStore } from '@crisol/store';
import type { Category, CategoryKind, Transaction, TransactionFlow } from '@crisol/types';
import {
  colors,
  fontSize,
  fontWeight,
  formatAmount,
  formatDate,
  radius,
  spacing,
} from '@crisol/ui';

import { Button } from '@/components/ui/button';
import { CategoryChip } from '@/components/ui/category-chip';
import { DataTable, type DataTableColumn } from '@/components/ui/data-table';
import { OriginBadge } from '@/components/ui/origin-badge';

export interface TransactionListProps {
  items: Transaction[];
  categories: Category[];
  onDelete: (id: string) => void;
  /**
   * PHASE-19.3: deshace la transferencia interna de la que la
   * transacción forma parte. Sólo se muestra el botón cuando la fila
   * tiene `transfer_pair_id !== null`. Si no se pasa el handler, el
   * botón no aparece (callers que no admitan esta acción).
   */
  onUnlinkTransfer?: ((id: string) => void) | undefined;
  deletingId?: string | null;
  unlinkingId?: string | null | undefined;
  /**
   * PHASE-34 — selección por checkbox para acciones en bloque. Si se pasa
   * `onToggleSelect`, se muestra una columna de checkboxes (cabecera =
   * "seleccionar todo"). Sin él, la tabla se comporta como antes.
   */
  selectedIds?: ReadonlySet<string> | undefined;
  onToggleSelect?: ((id: string) => void) | undefined;
  onToggleSelectAll?: (() => void) | undefined;
  allSelected?: boolean | undefined;
  someSelected?: boolean | undefined;
}

interface TransactionRow {
  tx: Transaction;
  category: Category | undefined;
}

/**
 * ADR-0004: el signo/color del importe lo manda `tx.flow`, no la categoría.
 * IN→income, OUT→expense, TRANSFER_*→neutro (fuera del cashflow). Devuelve
 * `undefined` si no hay flow, para que el caller use el fallback por categoría
 * (filas heredadas sin flow — el puente que 34.6 retira).
 */
function kindFromFlow(
  flow: TransactionFlow | null | undefined,
): CategoryKind | null | undefined {
  if (flow === 'IN') return 'income';
  if (flow === 'OUT') return 'expense';
  if (flow === 'TRANSFER_IN' || flow === 'TRANSFER_OUT') return null;
  return undefined;
}

function amountColorFor(kind: CategoryKind | null | undefined): string {
  if (kind === 'income') return colors.income;
  if (kind === 'expense') return colors.expense;
  return colors.text;
}

function amountSignFor(kind: CategoryKind | null | undefined): string {
  if (kind === 'income') return '+';
  if (kind === 'expense') return '-';
  return '';
}

export function TransactionList({
  items,
  categories,
  onDelete,
  onUnlinkTransfer,
  deletingId,
  unlinkingId,
  selectedIds,
  onToggleSelect,
  onToggleSelectAll,
  allSelected,
  someSelected,
}: TransactionListProps) {
  const router = useRouter();
  const activeCurrency = useCurrencyStore((s) => s.currency);
  const convertAll = useCurrencyStore((s) => s.convertAll);

  // AUDIT-2026-05: índice por id (O(1) lookup) en vez de `categories.find`
  // por cada fila (O(filas × categorías)). Memoizado para no reconstruir
  // el Map ni las filas en cada render que no cambie items/categorías.
  const categoryById = useMemo(
    () => new Map(categories.map((c) => [c.id, c])),
    [categories],
  );
  const rows: TransactionRow[] = useMemo(
    () =>
      items.map((tx) => ({
        tx,
        category: tx.category_id ? categoryById.get(tx.category_id) : undefined,
      })),
    [items, categoryById],
  );

  const selectionColumn: DataTableColumn<TransactionRow> = {
    key: 'select',
    header: (
      <input
        type="checkbox"
        aria-label="Seleccionar todo"
        checked={allSelected ?? false}
        ref={(el) => {
          if (el) el.indeterminate = !(allSelected ?? false) && (someSelected ?? false);
        }}
        onChange={() => onToggleSelectAll?.()}
        onClick={(e) => e.stopPropagation()}
        style={{ cursor: 'pointer', accentColor: colors.primary, width: 16, height: 16 }}
      />
    ),
    width: 44,
    render: ({ tx }) => (
      <input
        type="checkbox"
        aria-label="Seleccionar transacción"
        checked={selectedIds?.has(tx.id) ?? false}
        onChange={() => onToggleSelect?.(tx.id)}
        onClick={(e) => e.stopPropagation()}
        style={{ cursor: 'pointer', accentColor: colors.primary, width: 16, height: 16 }}
      />
    ),
  };

  const columns: DataTableColumn<TransactionRow>[] = [
    {
      key: 'date',
      header: 'Fecha',
      width: 120,
      render: ({ tx }) => (
        <span
          style={{
            fontSize: fontSize.sm,
            color: colors.text,
            whiteSpace: 'nowrap',
          }}
        >
          {formatDate(tx.occurred_at)}
        </span>
      ),
    },
    {
      key: 'category',
      header: 'Categoría',
      render: ({ category }) => (
        <CategoryChip
          label={category?.name ?? 'Sin categoría'}
          kind={category?.kind ?? null}
          color={category?.color ?? null}
          icon={category?.icon ?? null}
        />
      ),
    },
    {
      key: 'description',
      header: 'Descripción',
      render: ({ tx, category }) => (
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: spacing.xs,
            maxWidth: 320,
          }}
        >
          <span
            style={{
              fontSize: fontSize.sm,
              fontWeight: fontWeight.medium,
              color: tx.description ? colors.text : colors.textSubtle,
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              minWidth: 0,
            }}
          >
            {tx.description ?? '(sin descripción)'}
          </span>
          {tx.transfer_pair_id !== null || category?.is_transfer ? (
            <TransferBadge tx={tx} />
          ) : null}
        </span>
      ),
    },
    {
      key: 'origin',
      header: 'Origen',
      render: ({ tx }) => <OriginBadge source={tx.source} />,
    },
    {
      key: 'amount',
      header: 'Importe',
      align: 'right',
      width: 160,
      render: ({ tx, category }) => {
        // ADR-0004 (AUDIT-2026-07): el signo/color lo manda `tx.flow`. Una
        // pata de transferencia/deuda (TRANSFER_*) es neutra: fuera del
        // cashflow y (en deuda) aporta 0 al patrimonio — el badge
        // "Deuda"/"Transferencia" ya explica la fila. Sólo cae al fallback por
        // categoría cuando la fila no tiene flow (heredada).
        const flowKind = kindFromFlow(tx.flow);
        const isTransferLike =
          tx.transfer_pair_id !== null || category?.is_transfer === true;
        const displayKind =
          flowKind !== undefined
            ? flowKind
            : isTransferLike
              ? null
              : (category?.kind ?? null);
        // PHASE-8.4: el backend convierte per-row cuando el toggle
        // está ON (la página pasa `target_currency`). La fila trae
        // `converted_amount` listo, o `null` si no hay tasa para esa
        // fecha — en cuyo caso pintamos "≈ —" como señal de missing.
        const currenciesDiffer =
          tx.currency.toUpperCase() !== activeCurrency.toUpperCase();
        const showConverted = convertAll && currenciesDiffer;
        const convertedDisplay = (() => {
          if (!showConverted) return null;
          if (tx.converted_amount == null || tx.converted_currency == null) {
            return { text: '≈ —', tooltip: 'Sin tasa para esa fecha' };
          }
          return {
            text: `≈ ${formatAmount(tx.converted_amount, tx.converted_currency)}`,
            tooltip: `${tx.currency} ${formatAmount(tx.amount, tx.currency)} convertido a ${tx.converted_currency} con la tasa del ${tx.occurred_at.slice(0, 10)}`,
          };
        })();
        return (
          <span
            style={{
              display: 'inline-flex',
              flexDirection: 'column',
              alignItems: 'flex-end',
              lineHeight: 1.15,
            }}
          >
            <span
              style={{
                fontSize: fontSize.sm,
                fontWeight: fontWeight.semibold,
                color: amountColorFor(displayKind),
                fontVariantNumeric: 'tabular-nums',
                whiteSpace: 'nowrap',
              }}
            >
              {amountSignFor(displayKind)}
              {formatAmount(tx.amount, tx.currency)}
            </span>
            {convertedDisplay ? (
              <span
                title={convertedDisplay.tooltip}
                style={{
                  fontSize: fontSize.xs,
                  color: colors.textSubtle,
                  fontVariantNumeric: 'tabular-nums',
                  whiteSpace: 'nowrap',
                  marginTop: 1,
                }}
              >
                {convertedDisplay.text}
              </span>
            ) : null}
          </span>
        );
      },
    },
    {
      key: 'actions',
      header: '',
      align: 'right',
      width: onUnlinkTransfer ? 200 : 100,
      render: ({ tx }) => {
        const showUnlink =
          onUnlinkTransfer !== undefined && tx.transfer_pair_id !== null;
        const isUnlinking = unlinkingId === tx.id;
        return (
          <span
            onClick={(e) => e.stopPropagation()}
            onKeyDown={(e) => e.stopPropagation()}
            style={{ display: 'inline-flex', gap: spacing.xs, justifyContent: 'flex-end' }}
          >
            {showUnlink ? (
              <Button
                variant="ghost"
                onClick={() => onUnlinkTransfer(tx.id)}
                disabled={isUnlinking}
              >
                {isUnlinking ? 'Deshaciendo…' : 'Deshacer'}
              </Button>
            ) : null}
            <Button
              variant="ghost"
              onClick={() => onDelete(tx.id)}
              disabled={deletingId === tx.id}
              style={{ color: colors.danger, borderColor: colors.border }}
            >
              {deletingId === tx.id ? 'Borrando…' : 'Borrar'}
            </Button>
          </span>
        );
      },
    },
  ];

  return (
    <DataTable
      columns={onToggleSelect ? [selectionColumn, ...columns] : columns}
      rows={rows}
      rowKey={(row) => row.tx.id}
      onRowClick={(row) =>
        router.push(`/personal-finance/transactions/${row.tx.id}` as never)
      }
      rowAriaLabel={({ tx }) =>
        `Ver transacción del ${formatDate(tx.occurred_at)} por ${formatAmount(tx.amount, tx.currency)}`
      }
      emptyMessage="Sin transacciones con los filtros actuales."
    />
  );
}

/**
 * P3 (transfers-ux) — el badge distingue TRES estados, que antes
 * colapsaban en un único "Transferencia":
 *  - "Deuda": pata de una operación financiada (activo↔pasivo).
 *  - "Transferencia": par interno activo↔activo, con contraparte.
 *  - "Sin pareja" (tono aviso): categoría is_transfer pero SIN
 *    `transfer_pair_id` — está fuera del cashflow pero no enlazada a
 *    ninguna contraparte. Antes mostraba el mismo chip que un par real,
 *    así que el usuario creía "ya está" cuando faltaba enlazarla.
 */
function badgeFor(tx: Transaction): {
  label: string;
  title: string;
  tone: 'info' | 'warning';
} {
  if (tx.is_debt_pair) {
    return {
      label: 'Deuda',
      title: 'Operación financiada, enlazada a una cuenta de deuda.',
      tone: 'info',
    };
  }
  if (tx.transfer_pair_id !== null) {
    return {
      label: 'Transferencia',
      title: 'Movimiento entre tus cuentas, emparejado con su contraparte.',
      tone: 'info',
    };
  }
  return {
    label: 'Sin pareja',
    title: 'Marcada como transferencia pero sin contraparte. Enlázala desde Transferencias.',
    tone: 'warning',
  };
}

/**
 * Chip informativo (no clicable: "Deshacer"/"Borrar" viven en la columna
 * de acciones). El tono `warning` señala una transferencia incompleta.
 */
function TransferBadge({ tx }: { tx: Transaction }) {
  const { label, title, tone } = badgeFor(tx);
  const bg = tone === 'warning' ? colors.warningSoft : colors.primarySoft;
  const fg = tone === 'warning' ? colors.warning : colors.primary;
  return (
    <span
      title={title}
      style={{
        display: 'inline-block',
        padding: `${spacing.xs / 2}px ${spacing.sm}px`,
        backgroundColor: bg,
        color: fg,
        borderRadius: radius.sm,
        fontSize: fontSize.xs,
        fontWeight: fontWeight.semibold,
        textTransform: 'uppercase',
        letterSpacing: '0.04em',
        whiteSpace: 'nowrap',
        flex: '0 0 auto',
      }}
    >
      {label}
    </span>
  );
}
