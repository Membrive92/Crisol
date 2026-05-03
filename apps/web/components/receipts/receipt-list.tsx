'use client';

import { useRouter } from 'next/navigation';

import type { Receipt } from '@finanzas/types';
import { colors, fontSize, fontWeight, formatDate } from '@finanzas/ui';

import { DataTable, type DataTableColumn } from '@/components/ui/data-table';

import { ReceiptStatusBadge } from './status-badge';

export interface ReceiptListProps {
  items: Receipt[];
}

export function ReceiptList({ items }: ReceiptListProps) {
  const router = useRouter();

  const columns: DataTableColumn<Receipt>[] = [
    {
      key: 'date',
      header: 'Fecha',
      width: 120,
      render: (r) => (
        <span
          style={{
            fontSize: fontSize.sm,
            color: colors.text,
            whiteSpace: 'nowrap',
          }}
        >
          {formatDate(r.created_at)}
        </span>
      ),
    },
    {
      key: 'merchant',
      header: 'Comercio',
      render: (r) => {
        const merchant = pickMerchant(r);
        return (
          <span
            style={{
              fontSize: fontSize.sm,
              fontWeight: fontWeight.medium,
              color: merchant ? colors.text : colors.textSubtle,
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              display: 'inline-block',
              maxWidth: 320,
            }}
          >
            {merchant ?? '(sin comercio)'}
          </span>
        );
      },
    },
    {
      key: 'total',
      header: 'Total',
      align: 'right',
      width: 140,
      render: (r) => {
        const total = pickTotal(r);
        return (
          <span
            style={{
              fontSize: fontSize.sm,
              fontWeight: fontWeight.semibold,
              color: total ? colors.text : colors.textSubtle,
              fontVariantNumeric: 'tabular-nums',
              whiteSpace: 'nowrap',
            }}
          >
            {total ?? '—'}
          </span>
        );
      },
    },
    {
      key: 'status',
      header: 'Estado',
      align: 'right',
      width: 140,
      render: (r) => <ReceiptStatusBadge status={r.status} />,
    },
  ];

  return (
    <DataTable
      columns={columns}
      rows={items}
      rowKey={(r) => r.id}
      onRowClick={(r) =>
        router.push(`/personal-finance/receipts/${r.id}` as never)
      }
      emptyMessage="Aún no has subido tickets."
    />
  );
}

function pickMerchant(r: Receipt): string | null {
  const ext = r.extraction as Record<string, unknown>;
  const merchant = ext['merchant'];
  return typeof merchant === 'string' ? merchant : null;
}

function pickTotal(r: Receipt): string | null {
  const ext = r.extraction as Record<string, unknown>;
  const total = ext['total'];
  const currency = ext['currency'] ?? 'EUR';
  if (typeof total !== 'string') return null;
  return `${total} ${typeof currency === 'string' ? currency : ''}`.trim();
}
