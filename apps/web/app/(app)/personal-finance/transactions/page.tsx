'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';

import {
  useCategories,
  useDeleteTransaction,
  useRestoreTransaction,
  useTransactions,
  useTrashedTransactions,
} from '@finanzas/services';
import { toast, useCurrencyStore } from '@finanzas/store';
import type { TransactionListQuery } from '@finanzas/types';
import { colors, fontSize, fontWeight, spacing } from '@finanzas/ui';

import { StitchSearchToolbar } from '@/components/transactions/stitch-search-toolbar';
import { StitchTransactionsKpiRow } from '@/components/transactions/stitch-transactions-kpi-row';
import { TransactionList } from '@/components/transactions/transaction-list';
import { Button } from '@/components/ui/button';
import { Pagination } from '@/components/ui/pagination';
import { PlusIcon, ReceiptIcon, UploadIcon } from '@/components/ui/icons';

const PAGE_SIZE = 20;

export default function TransactionsPage() {
  const [filters, setFilters] = useState<TransactionListQuery>({
    limit: PAGE_SIZE,
    offset: 0,
  });
  const currency = useCurrencyStore((s) => s.currency);
  const convertAll = useCurrencyStore((s) => s.convertAll);

  // PHASE-8.4: cuando el toggle global está ON, pedimos al backend la
  // conversión per-row con `target_currency`. La tabla recibe
  // `converted_amount`/`converted_currency` ya hechos y deja de
  // necesitar `useQueries` por fecha en cliente.
  const queryParams = useMemo<TransactionListQuery>(
    () => (convertAll ? { ...filters, target_currency: currency } : filters),
    [filters, convertAll, currency],
  );

  const { data, isLoading, isError, error, isFetching } = useTransactions(queryParams);
  const { data: categories } = useCategories();
  const deleteMutation = useDeleteTransaction();
  const restoreMutation = useRestoreTransaction();
  // Conteo de papelera para mostrar badge cuando hay items.
  const trashCountQuery = useTrashedTransactions({ limit: 1 });
  const trashCount = trashCountQuery.data?.total ?? 0;

  const total = data?.total ?? 0;
  const items = data?.items ?? [];
  const offset = filters.offset ?? 0;
  const limit = filters.limit ?? PAGE_SIZE;

  // Periodo para los KPIs: el rango activo del filtro o todo el año
  // actual si no hay rango.
  const now = new Date();
  const dateFrom = filters.date_from ?? new Date(now.getFullYear(), 0, 1).toISOString();
  const dateTo =
    filters.date_to ?? new Date(now.getFullYear(), 11, 31, 23, 59, 59).toISOString();

  function handleDelete(id: string) {
    if (!confirm('¿Mover esta transacción a la papelera?')) return;
    deleteMutation.mutate(id, {
      onSuccess: () => {
        // PHASE-11.3: el banner inline ad-hoc fue reemplazado por un
        // toast global con acción [Deshacer]. Al pulsar Deshacer se
        // dispara el restore y el toast se cierra solo (lo gestiona
        // el ToastCard tras invocar la action).
        toast.show({
          kind: 'info',
          message: 'Transacción movida a papelera.',
          action: {
            label: 'Deshacer',
            onPress: () => restoreMutation.mutate(id),
          },
        });
      },
    });
  }

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', padding: spacing.lg }}>
      {/* Eyebrow bar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: `${spacing.sm}px 0 ${spacing.md}px`,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: spacing.xs }}>
          <span
            aria-hidden
            style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              backgroundColor: colors.primary,
            }}
          />
          <span
            style={{
              fontSize: fontSize.sm,
              fontWeight: fontWeight.semibold,
              color: colors.text,
            }}
          >
            Transacciones
          </span>
          <span
            style={{
              fontSize: fontSize.sm,
              color: colors.textMuted,
              marginLeft: spacing.sm,
            }}
          >
            {total} {total === 1 ? 'registro' : 'registros'}
            {isFetching ? ' · actualizando…' : ''}
          </span>
        </div>
        {/* Acciones de entrada de datos. La primaria es "Nueva
            transacción" (manual). Importar (CSV/XLSX/PDF) y Capturar
            ticket (foto + IA local) son flujos secundarios — viven aquí
            porque conceptualmente son "otras formas de añadir
            transacciones", no pestañas independientes. */}
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: spacing.sm }}>
          <Link href="/personal-finance/trash">
            <Button variant="ghost">
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                Papelera
                {trashCount > 0 ? (
                  <span
                    aria-label={`${trashCount} en papelera`}
                    style={{
                      minWidth: 18,
                      height: 18,
                      padding: '0 5px',
                      borderRadius: 9,
                      backgroundColor: colors.primary,
                      color: colors.onPrimary,
                      fontSize: 10,
                      fontWeight: fontWeight.bold,
                      display: 'inline-flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      lineHeight: 1,
                    }}
                  >
                    {trashCount}
                  </span>
                ) : null}
              </span>
            </Button>
          </Link>
          <Link href="/personal-finance/imports">
            <Button variant="ghost">
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                <UploadIcon size={14} />
                Importar
              </span>
            </Button>
          </Link>
          <Link href="/personal-finance/receipts">
            <Button variant="ghost">
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                <ReceiptIcon size={14} />
                Capturar ticket
              </span>
            </Button>
          </Link>
          <Link href="/personal-finance/transactions/new">
            <Button variant="secondary">
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                <PlusIcon size={14} />
                Nueva transacción
              </span>
            </Button>
          </Link>
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.lg }}>
        <StitchTransactionsKpiRow
          currency={currency}
          dateFrom={dateFrom}
          dateTo={dateTo}
        />

        <StitchSearchToolbar
          value={filters}
          onChange={setFilters}
          categories={categories ?? []}
        />

        {isLoading ? (
          <p style={{ color: colors.textMuted }}>Cargando…</p>
        ) : isError ? (
          <p style={{ color: colors.danger }}>
            Error: {error instanceof Error ? error.message : 'desconocido'}
          </p>
        ) : (
          <>
            <TransactionList
              items={items}
              categories={categories ?? []}
              onDelete={handleDelete}
              deletingId={
                deleteMutation.isPending ? (deleteMutation.variables as string) : null
              }
            />

            <Pagination
              total={total}
              offset={offset}
              limit={limit}
              pageItemCount={items.length}
              onChange={(nextOffset) => setFilters({ ...filters, offset: nextOffset })}
            />
          </>
        )}
      </div>
    </div>
  );
}
