'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';

import {
  useAccounts,
  useBulkDeleteTransactions,
  useCategories,
  useDeleteTransaction,
  useRestoreTransaction,
  useTransactions,
  useTrashedTransactions,
  useUnlinkTransfer,
} from '@crisol/services';
import { toast, useCurrencyStore } from '@crisol/store';
import type { TransactionListQuery } from '@crisol/types';
import { colors, fontSize, fontWeight, spacing } from '@crisol/ui';

import { StitchSearchToolbar } from '@/components/transactions/stitch-search-toolbar';
import { StitchTransactionsKpiRow } from '@/components/transactions/stitch-transactions-kpi-row';
import { TransactionList } from '@/components/transactions/transaction-list';
import { Button } from '@/components/ui/button';
import { ConfirmDialog } from '@/components/ui/confirm-dialog';
import { Pagination } from '@/components/ui/pagination';
import { PlusIcon, ReceiptIcon, UploadIcon } from '@/components/ui/icons';

const PAGE_SIZE = 20;

export default function TransactionsPage() {
  // Sincronizamos TODOS los filtros con la URL para que al volver del
  // detalle de una transacción (o tras refrescar / abrir un link
  // compartido) el usuario aterrice en la misma página y con los
  // mismos filtros que tenía aplicados. El estado vive en el
  // componente; añadimos un puente bidireccional con la URL.
  const searchParams = useSearchParams();
  const router = useRouter();

  const [filters, setFiltersState] = useState<TransactionListQuery>(() =>
    filtersFromSearchParams(searchParams),
  );

  function setFilters(next: TransactionListQuery) {
    setFiltersState(next);
    const qs = filtersToSearchParams(next).toString();
    // `replace` (no `push`) para no inflar el historial con un entry
    // por cada cambio de filtro o cambio de página — el botón
    // "atrás" del navegador debe seguir saliendo de la lista, no
    // recorrer paginación.
    router.replace(
      `/personal-finance/transactions${qs ? `?${qs}` : ''}`,
      { scroll: false },
    );
  }
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
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
  // includeArchived: el filtro de cuenta tiene que poder seleccionar
  // archivadas porque históricamente puede tener movimientos.
  const { data: accounts } = useAccounts({ includeArchived: true });
  const deleteMutation = useDeleteTransaction();
  const restoreMutation = useRestoreTransaction();
  const bulkDeleteMutation = useBulkDeleteTransactions();
  const unlinkTransferMutation = useUnlinkTransfer();
  // Conteo de papelera para mostrar badge cuando hay items.
  const trashCountQuery = useTrashedTransactions({ limit: 1 });
  const trashCount = trashCountQuery.data?.total ?? 0;
  const [confirmingBulkDelete, setConfirmingBulkDelete] = useState(false);

  const total = data?.total ?? 0;
  const items = data?.items ?? [];
  const offset = filters.offset ?? 0;
  const limit = filters.limit ?? PAGE_SIZE;
  const hasActiveFilters = Boolean(
    filters.account_id ||
      filters.category_id ||
      filters.date_from ||
      filters.date_to ||
      filters.search,
  );

  // Periodo para los KPIs: el rango activo del filtro o todo el año
  // actual si no hay rango.
  const now = new Date();
  const dateFrom = filters.date_from ?? new Date(now.getFullYear(), 0, 1).toISOString();
  const dateTo =
    filters.date_to ?? new Date(now.getFullYear(), 11, 31, 23, 59, 59).toISOString();

  function handleDelete(id: string) {
    setPendingDeleteId(id);
  }

  function handleUnlinkTransfer(id: string) {
    unlinkTransferMutation.mutate(id, {
      onSuccess: () => toast.info('Transferencia interna deshecha.'),
      onError: () =>
        toast.error('No se pudo deshacer la transferencia.'),
    });
  }

  function confirmBulkDelete() {
    setConfirmingBulkDelete(false);
    // Mandamos sólo los filtros que tienen valor para que el backend
    // los aplique igual que en el listado. `limit`/`offset` son de
    // paginación: se omiten porque el bulk afecta a todas las filas
    // que matcheen, no sólo a la página actual.
    const { account_id, category_id, date_from, date_to, search } = filters;
    bulkDeleteMutation.mutate(
      {
        ...(account_id ? { account_id } : {}),
        ...(category_id ? { category_id } : {}),
        ...(date_from ? { date_from } : {}),
        ...(date_to ? { date_to } : {}),
        ...(search ? { search } : {}),
      },
      {
        onSuccess: ({ deleted_count }) => {
          if (deleted_count === 0) {
            toast.info('No había transacciones que mover.');
            return;
          }
          toast.success(
            `Movidas ${deleted_count} ${
              deleted_count === 1 ? 'transacción' : 'transacciones'
            } a papelera.`,
          );
        },
        onError: (err) => {
          toast.error(
            err instanceof Error
              ? `Error al borrar: ${err.message}`
              : 'Error al borrar transacciones',
          );
        },
      },
    );
  }

  function confirmDelete() {
    const id = pendingDeleteId;
    if (!id) return;
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
    setPendingDeleteId(null);
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
          accounts={accounts ?? []}
        />

        {isLoading ? (
          <p style={{ color: colors.textMuted }}>Cargando…</p>
        ) : isError ? (
          <p style={{ color: colors.danger }}>
            Error: {error instanceof Error ? error.message : 'desconocido'}
          </p>
        ) : (
          <>
            {/* Barra de acciones bulk encima de la tabla. El botón
                "Mover a papelera" usa los filtros activos: si no hay
                filtros mueve TODO; si hay filtros (categoría, rango,
                búsqueda) mueve sólo lo que matchea. Alineado con la
                columna de acciones por fila a la derecha. */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: spacing.sm,
              }}
            >
              <span style={{ fontSize: fontSize.xs, color: colors.textMuted }}>
                {hasActiveFilters
                  ? `${total} ${total === 1 ? 'resultado' : 'resultados'} con los filtros activos`
                  : `${total} ${total === 1 ? 'transacción' : 'transacciones'} en total`}
              </span>
              <Button
                variant="ghost"
                onClick={() => setConfirmingBulkDelete(true)}
                disabled={total === 0 || bulkDeleteMutation.isPending}
                style={{ color: colors.danger, borderColor: colors.danger }}
              >
                {bulkDeleteMutation.isPending ? 'Borrando…' : 'Borrar todo'}
              </Button>
            </div>

            <TransactionList
              items={items}
              categories={categories ?? []}
              onDelete={handleDelete}
              onUnlinkTransfer={handleUnlinkTransfer}
              deletingId={
                deleteMutation.isPending ? (deleteMutation.variables as string) : null
              }
              unlinkingId={
                unlinkTransferMutation.isPending
                  ? (unlinkTransferMutation.variables as string)
                  : null
              }
            />

            <Pagination
              total={total}
              offset={offset}
              limit={limit}
              pageItemCount={items.length}
              onChange={(nextOffset) =>
                setFilters({ ...filters, offset: nextOffset })
              }
            />
          </>
        )}
      </div>

      <ConfirmDialog
        open={pendingDeleteId !== null}
        title="¿Mover a la papelera?"
        description="Podrás restaurarla desde la papelera o usar Deshacer en el toast."
        confirmLabel="Mover"
        tone="danger"
        loading={deleteMutation.isPending}
        onConfirm={confirmDelete}
        onCancel={() => setPendingDeleteId(null)}
      />

      <ConfirmDialog
        open={confirmingBulkDelete}
        title={
          hasActiveFilters
            ? `¿Mover ${total} ${total === 1 ? 'transacción' : 'transacciones'} a papelera?`
            : '¿Mover todas las transacciones a papelera?'
        }
        description={
          hasActiveFilters
            ? 'Solo se moverán las que coinciden con los filtros activos. Podrás restaurarlas individualmente desde la papelera.'
            : 'Se moverán TODAS tus transacciones activas. Podrás restaurarlas individualmente desde la papelera.'
        }
        confirmLabel="Mover a papelera"
        tone="danger"
        loading={bulkDeleteMutation.isPending}
        onConfirm={confirmBulkDelete}
        onCancel={() => setConfirmingBulkDelete(false)}
      />

    </div>
  );
}

/**
 * Reconstruye el estado de filtros desde la query string. Omitimos
 * propiedades no presentes en lugar de ponerlas a `undefined`
 * explícito (TS strict + `exactOptionalPropertyTypes` lo prohíbe).
 * `limit` se fuerza al PAGE_SIZE — no es algo que el usuario controle
 * desde la UI, así que no merece la pena meterlo en la URL.
 */
function filtersFromSearchParams(
  searchParams: ReturnType<typeof useSearchParams>,
): TransactionListQuery {
  const rawOffset = searchParams.get('offset');
  const parsedOffset = rawOffset ? Number(rawOffset) : 0;
  const offset =
    Number.isFinite(parsedOffset) && parsedOffset > 0
      ? Math.floor(parsedOffset)
      : 0;
  const accountId = searchParams.get('account_id');
  const categoryId = searchParams.get('category_id');
  const dateFrom = searchParams.get('date_from');
  const dateTo = searchParams.get('date_to');
  const search = searchParams.get('search');
  return {
    limit: PAGE_SIZE,
    offset,
    ...(accountId ? { account_id: accountId } : {}),
    ...(categoryId ? { category_id: categoryId } : {}),
    ...(dateFrom ? { date_from: dateFrom } : {}),
    ...(dateTo ? { date_to: dateTo } : {}),
    ...(search ? { search } : {}),
  };
}

/**
 * Inverso de `filtersFromSearchParams`. `target_currency` y `limit`
 * NO viajan a la URL: el primero lo deriva el page del store global,
 * el segundo es fijo.
 */
function filtersToSearchParams(filters: TransactionListQuery): URLSearchParams {
  const sp = new URLSearchParams();
  if (filters.offset && filters.offset > 0) {
    sp.set('offset', String(filters.offset));
  }
  if (filters.account_id) sp.set('account_id', filters.account_id);
  if (filters.category_id) sp.set('category_id', filters.category_id);
  if (filters.date_from) sp.set('date_from', filters.date_from);
  if (filters.date_to) sp.set('date_to', filters.date_to);
  if (filters.search) sp.set('search', filters.search);
  return sp;
}
