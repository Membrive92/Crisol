'use client';

import { useRouter } from 'next/navigation';

import type { ImportJob } from '@finanzas/types';
import { colors, fontSize, fontWeight, formatDate } from '@finanzas/ui';

import { DataTable, type DataTableColumn } from '@/components/ui/data-table';

import { StatusBadge } from './status-badge';

export interface ImportListProps {
  items: ImportJob[];
}

export function ImportList({ items }: ImportListProps) {
  const router = useRouter();

  const columns: DataTableColumn<ImportJob>[] = [
    {
      key: 'date',
      header: 'Fecha',
      width: 120,
      render: (job) => (
        <span
          style={{
            fontSize: fontSize.sm,
            color: colors.text,
            whiteSpace: 'nowrap',
          }}
        >
          {formatDate(job.created_at)}
        </span>
      ),
    },
    {
      key: 'filename',
      header: 'Archivo',
      render: (job) => (
        <span
          style={{
            fontSize: fontSize.sm,
            fontWeight: fontWeight.medium,
            color: colors.text,
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            display: 'inline-block',
            maxWidth: 320,
          }}
        >
          {job.filename}
        </span>
      ),
    },
    {
      key: 'rows',
      header: 'Resultado',
      render: (job) => (
        <span
          style={{
            fontSize: fontSize.xs,
            color: colors.textMuted,
            fontVariantNumeric: 'tabular-nums',
            whiteSpace: 'nowrap',
          }}
        >
          <span style={{ color: colors.success, fontWeight: fontWeight.semibold }}>
            {job.rows_ok}
          </span>{' '}
          ok ·{' '}
          <span style={{ color: colors.warning, fontWeight: fontWeight.semibold }}>
            {job.rows_skipped}
          </span>{' '}
          dup ·{' '}
          <span style={{ color: colors.danger, fontWeight: fontWeight.semibold }}>
            {job.rows_failed}
          </span>{' '}
          err
        </span>
      ),
    },
    {
      key: 'status',
      header: 'Estado',
      align: 'right',
      width: 140,
      render: (job) => <StatusBadge status={job.status} />,
    },
  ];

  return (
    <DataTable
      columns={columns}
      rows={items}
      rowKey={(job) => job.id}
      onRowClick={(job) =>
        router.push(`/personal-finance/imports/${job.id}` as never)
      }
      emptyMessage="Aún no has importado ningún fichero."
    />
  );
}
