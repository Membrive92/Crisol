'use client';

import { useState } from 'react';

import {
  formatApiError,
  useMisclassifiedTransfers,
  useReclassifyBulk,
} from '@crisol/services';
import { toast } from '@crisol/store';
import type { MisclassifiedTransfer } from '@crisol/types';
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
import { Card } from '@/components/ui/card';
import { AlertTriangleIcon } from '@/components/ui/icons';

const KIND_LABEL: Record<string, string> = {
  income: 'ingreso',
  expense: 'gasto',
};

/**
 * PHASE-31.2 / PHASE-41 — Banner de data-hygiene en Transacciones que
 * lista las tx con categoría `is_transfer=true` cuya dirección
 * (income/expense) no coincide con lo que indica la descripción, y
 * permite reclasificarlas en bloque al kind opuesto. Vivía en la
 * pestaña `/transfers`; al retirarse esa pestaña (ADR-0005) la
 * corrección de dirección se hace desde aquí, junto al resto de la
 * higiene del libro mayor. La sección sólo aparece cuando hay tx
 * detectadas (devuelve `null` en caso contrario → cero ruido).
 *
 * Diseño: card con tono `warning-soft`; checklist con sugerencia
 * individual; acciones inferiores [Seleccionar todas] / [Re-categorizar].
 */
export function MisclassifiedSection() {
  const { data, isLoading } = useMisclassifiedTransfers();
  const reclassifyMutation = useReclassifyBulk();
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const items = data ?? [];

  if (isLoading || items.length === 0) return null;

  const allSelected = selectedIds.size === items.length;
  const someSelected = selectedIds.size > 0;

  function toggleOne(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleAll() {
    if (allSelected) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(items.map((i) => i.transaction_id)));
    }
  }

  function handleReclassify() {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;
    reclassifyMutation.mutate(
      { transaction_ids: ids },
      {
        onSuccess: (resp) => {
          toast.success(
            `Re-categorizadas ${resp.reclassified} ${
              resp.reclassified === 1 ? 'transacción' : 'transacciones'
            }.`,
          );
          if (resp.errors.length > 0) {
            toast.error(
              `${resp.errors.length} no se pudieron procesar: ${resp.errors[0]}`,
            );
          }
          setSelectedIds(new Set());
        },
        onError: (err) =>
          toast.error(
            formatApiError(err, 'No se pudieron re-categorizar las transferencias'),
          ),
      },
    );
  }

  return (
    <Card
      style={{
        padding: spacing.lg,
        backgroundColor: colors.warningSoft,
        border: `1px solid ${colors.warning}`,
        display: 'flex',
        flexDirection: 'column',
        gap: spacing.md,
      }}
    >
      <header
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          gap: spacing.sm,
        }}
      >
        <span
          aria-hidden
          style={{
            color: colors.warning,
            flex: '0 0 auto',
            marginTop: 2,
          }}
        >
          <AlertTriangleIcon size={18} />
        </span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <h3
            style={{
              margin: 0,
              fontSize: fontSize.md,
              fontWeight: fontWeight.semibold,
              color: colors.text,
              letterSpacing: '-0.01em',
            }}
          >
            Transferencias posiblemente mal categorizadas
          </h3>
          <p
            style={{
              margin: `${spacing.xs}px 0 0`,
              fontSize: fontSize.sm,
              color: colors.text,
              lineHeight: 1.5,
            }}
          >
            Hemos detectado <strong>{items.length}</strong>{' '}
            {items.length === 1 ? 'transacción cuya' : 'transacciones cuyas'}{' '}
            categoría no coincide con la dirección del movimiento. Esto puede
            estar afectando al saldo de tus cuentas. Re-categoriza al kind
            opuesto con un click.
          </p>
        </div>
      </header>

      <ul
        style={{
          margin: 0,
          padding: 0,
          listStyle: 'none',
          display: 'flex',
          flexDirection: 'column',
          gap: spacing.xs,
          maxHeight: 360,
          overflowY: 'auto',
        }}
      >
        {items.map((item) => (
          <MisclassifiedRow
            key={item.transaction_id}
            item={item}
            checked={selectedIds.has(item.transaction_id)}
            onToggle={() => toggleOne(item.transaction_id)}
          />
        ))}
      </ul>

      <footer
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: spacing.sm,
          flexWrap: 'wrap',
        }}
      >
        <Button
          type="button"
          variant="ghost"
          onClick={toggleAll}
          disabled={reclassifyMutation.isPending}
        >
          {allSelected
            ? 'Deseleccionar todas'
            : `Seleccionar todas (${items.length})`}
        </Button>
        <Button
          type="button"
          variant="primary"
          onClick={handleReclassify}
          disabled={!someSelected || reclassifyMutation.isPending}
        >
          {reclassifyMutation.isPending
            ? 'Re-categorizando…'
            : `Re-categorizar las marcadas (${selectedIds.size})`}
        </Button>
      </footer>
    </Card>
  );
}

function MisclassifiedRow({
  item,
  checked,
  onToggle,
}: {
  item: MisclassifiedTransfer;
  checked: boolean;
  onToggle: () => void;
}) {
  const currentLabel = KIND_LABEL[item.current_category_kind] ?? item.current_category_kind;
  const suggestedLabel = KIND_LABEL[item.suggested_kind] ?? item.suggested_kind;
  return (
    <li
      style={{
        display: 'flex',
        gap: spacing.sm,
        padding: `${spacing.sm}px ${spacing.md}px`,
        backgroundColor: colors.surface,
        border: `1px solid ${colors.border}`,
        borderRadius: radius.sm,
      }}
    >
      <input
        type="checkbox"
        checked={checked}
        onChange={onToggle}
        aria-label={`Seleccionar ${item.description ?? item.transaction_id}`}
        style={{ marginTop: 4, flex: '0 0 auto', cursor: 'pointer' }}
      />
      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 2 }}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'baseline',
            gap: spacing.sm,
            fontSize: fontSize.sm,
            color: colors.text,
          }}
        >
          <span
            style={{
              flex: 1,
              minWidth: 0,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              fontWeight: fontWeight.medium,
            }}
          >
            {formatDate(item.occurred_at)} ·{' '}
            {item.description ?? '(sin descripción)'}
          </span>
          <span
            style={{
              fontVariantNumeric: 'tabular-nums',
              fontWeight: fontWeight.semibold,
              color: colors.text,
              whiteSpace: 'nowrap',
            }}
          >
            {formatAmount(item.amount, item.currency)}
          </span>
        </div>
        <div
          style={{
            fontSize: 11,
            color: colors.textMuted,
            lineHeight: 1.4,
          }}
        >
          Actual: <strong>{item.current_category_name}</strong> ({currentLabel}) ·
          sugerido: <strong style={{ color: colors.primary }}>{suggestedLabel}</strong>
        </div>
      </div>
    </li>
  );
}
