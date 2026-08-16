'use client';

import { useCallback, useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';

import {
  formatApiError,
  pickPreferredAccountId,
  useAccounts,
  useBulkCategorizeTransactions,
  useBulkDeleteTransactions,
  useCategories,
  useDeleteTransaction,
  useReassignAccount,
  useRestoreTransaction,
  useTransactions,
  useTrashedTransactions,
  useUnlinkTransfer,
} from '@crisol/services';
import { toast, useCurrencyStore } from '@crisol/store';
import type { TransactionListQuery } from '@crisol/types';
import { colors, fontSize, fontWeight, layout, pluralize, radius, spacing } from '@crisol/ui';

import { FinancingMatchesSection } from '@/components/transactions/financing-matches-section';
import { MisclassifiedSection } from '@/components/transactions/misclassified-section';
import { StitchSearchToolbar } from '@/components/transactions/stitch-search-toolbar';
import { StitchTransactionsKpiRow } from '@/components/transactions/stitch-transactions-kpi-row';
import { TransactionList } from '@/components/transactions/transaction-list';
import { UncategorizedBanner } from '@/components/transactions/uncategorized-banner';
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
    // La selección por checkbox es por página/filtro: al cambiar cualquiera,
    // los ids seleccionados pueden dejar de estar visibles → la vaciamos.
    setSelectedIds(new Set());
    setBulkCategoryId('');
    const qs = filtersToSearchParams(next).toString();
    // `replace` (no `push`) para no inflar el historial con un entry
    // por cada cambio de filtro o cambio de página — el botón
    // "atrás" del navegador debe seguir saliendo de la lista, no
    // recorrer paginación.
    router.replace(`/personal-finance/transactions${qs ? `?${qs}` : ''}`, { scroll: false });
  }
  // Las acciones en bloque arrancan plegadas: son destructivas o mueven
  // dinero de sitio, y tenerlas siempre a la vista hacía que su desplegable de
  // cuentas compitiera con el filtro.
  const [bulkOpen, setBulkOpen] = useState(false);
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
  const bulkCategorizeMutation = useBulkCategorizeTransactions();
  const reassignMutation = useReassignAccount();
  const unlinkTransferMutation = useUnlinkTransfer();
  // PHASE-34 — selección por checkbox para recategorizar en bloque.
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set());
  const [bulkCategoryId, setBulkCategoryId] = useState('');
  // Conteo de papelera para mostrar badge cuando hay items.
  const trashCountQuery = useTrashedTransactions({ limit: 1 });
  const trashCount = trashCountQuery.data?.total ?? 0;
  const [confirmingBulkDelete, setConfirmingBulkDelete] = useState(false);
  // PHASE-32 — reasignación en bloque a una cuenta (consolidar el mes en
  // la principal). El destino por defecto es la cuenta principal.
  const activeAccounts = (accounts ?? []).filter((a) => !a.is_archived);

  // PHASE-47.E — nombre del pasivo que aplazó una compra, para el hover del
  // asterisco. Se incluyen las archivadas a propósito: un recibo aplazado se
  // archiva en cuanto se termina de pagar, y sus compras siguen marcadas.
  const deferredLiabilityName = useCallback(
    (accountId: string) => (accounts ?? []).find((a) => a.id === accountId)?.name,
    [accounts],
  );
  const [reassignTargetId, setReassignTargetId] = useState('');
  // AUDIT MEDIUM#9 / LOW#14 — destino por defecto: la principal, o el primer
  // ACTIVO (nunca un pasivo), nunca '' (antes dejaba el botón deshabilitado).
  const reassignTarget = reassignTargetId || pickPreferredAccountId(accounts ?? []);
  const reassignTargetName =
    activeAccounts.find((a) => a.id === reassignTarget)?.name ?? 'la cuenta';
  const [confirmingReassign, setConfirmingReassign] = useState(false);

  const total = data?.total ?? 0;
  const items = data?.items ?? [];
  const offset = filters.offset ?? 0;
  const limit = filters.limit ?? PAGE_SIZE;
  const hasActiveFilters = Boolean(
    filters.account_id ||
    filters.category_id ||
    filters.uncategorized ||
    filters.date_from ||
    filters.date_to ||
    filters.search,
  );
  // Las acciones bulk (borrar todo / reasignar) NO aplican el filtro
  // "sin categoría" en el backend; con ese filtro activo operarían sobre
  // TODO el resto de filtros (vacíos) → borrarían/moverían todo. Se
  // deshabilitan mientras el filtro está activo (el flujo de "Ver y
  // categorizar" es clasificar una a una, no en bloque).
  const bulkDisabledByUncategorized = Boolean(filters.uncategorized);

  // PHASE-34 — selección por checkbox (sobre los items visibles de la página).
  const allSelected = items.length > 0 && items.every((t) => selectedIds.has(t.id));
  const someSelected = items.some((t) => selectedIds.has(t.id));
  // Categorías ofrecidas para recategorizar en bloque: excluimos las de
  // transferencia (asignarlas a un gasto normal lo dejaría como "sin pareja").
  const bulkCategoryOptions = (categories ?? []).filter((c) => !c.is_transfer);

  function toggleSelect(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }
  function toggleSelectAll() {
    setSelectedIds((prev) => {
      const allOnPage = items.length > 0 && items.every((t) => prev.has(t.id));
      return allOnPage ? new Set<string>() : new Set(items.map((t) => t.id));
    });
  }
  function applyBulkCategory() {
    if (selectedIds.size === 0 || !bulkCategoryId) return;
    bulkCategorizeMutation.mutate(
      { transactionIds: [...selectedIds], categoryId: bulkCategoryId },
      {
        onSuccess: ({ updated }) => {
          const catName =
            bulkCategoryOptions.find((c) => c.id === bulkCategoryId)?.name ?? 'la categoría';
          toast.success(
            `${updated} ${
              updated === 1 ? 'transacción recategorizada' : 'transacciones recategorizadas'
            } a "${catName}".`,
          );
          setSelectedIds(new Set());
          setBulkCategoryId('');
        },
        onError: (err) => toast.error(formatApiError(err, 'No se pudo recategorizar')),
      },
    );
  }

  // Periodo para los KPIs: el rango activo del filtro o todo el año
  // actual si no hay rango. AUDIT-2026-07 (LOW): límites por defecto en UTC
  // (`Date.UTC`), igual que el TimeSelector, para no desplazar la frontera del
  // año en Europe/Madrid.
  const now = new Date();
  const dateFrom = filters.date_from ?? new Date(Date.UTC(now.getFullYear(), 0, 1)).toISOString();
  const dateTo =
    filters.date_to ?? new Date(Date.UTC(now.getFullYear(), 11, 31, 23, 59, 59)).toISOString();

  function handleDelete(id: string) {
    setPendingDeleteId(id);
  }

  function handleUnlinkTransfer(id: string) {
    unlinkTransferMutation.mutate(id, {
      onSuccess: () => toast.info('Transferencia interna deshecha.'),
      onError: () => toast.error('No se pudo deshacer la transferencia.'),
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

  function confirmReassign() {
    setConfirmingReassign(false);
    if (!reassignTarget) return;
    const { account_id, category_id, date_from, date_to, search } = filters;
    reassignMutation.mutate(
      {
        targetAccountId: reassignTarget,
        filters: {
          ...(account_id ? { account_id } : {}),
          ...(category_id ? { category_id } : {}),
          ...(date_from ? { date_from } : {}),
          ...(date_to ? { date_to } : {}),
          ...(search ? { search } : {}),
        },
      },
      {
        onSuccess: ({ reassigned_count, skipped_other_currency }) => {
          // HIGH#3 — las tx de otra divisa NO se mueven (las sacaría del
          // saldo); el backend las cuenta aparte y aquí lo informamos.
          const skippedNote =
            skipped_other_currency > 0
              ? ` (${skipped_other_currency} ${pluralize(
                  skipped_other_currency,
                  'omitida',
                  'omitidas',
                )} por tener otra divisa)`
              : '';
          if (reassigned_count === 0) {
            toast.info(
              skipped_other_currency > 0
                ? `Nada movido${skippedNote}.`
                : 'Nada que mover (ya estaban en esa cuenta o son transferencias internas).',
            );
            return;
          }
          const accName = activeAccounts.find((a) => a.id === reassignTarget)?.name ?? 'la cuenta';
          toast.success(
            `Movidas ${reassigned_count} ${pluralize(
              reassigned_count,
              'transacción',
              'transacciones',
            )} a ${accName}.${skippedNote}`,
          );
        },
        onError: (err) => toast.error(formatApiError(err, 'No se pudo reasignar')),
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
    <div style={{ maxWidth: layout.pageWide, margin: '0 auto', padding: spacing.lg }}>
      {/* Eyebrow bar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          rowGap: spacing.sm,
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
        <div style={{ display: 'inline-flex', alignItems: 'center', flexWrap: 'wrap', rowGap: spacing.sm, gap: spacing.sm }}>
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
        <StitchTransactionsKpiRow currency={currency} dateFrom={dateFrom} dateTo={dateTo} />

        <UncategorizedBanner
          onSeeUncategorized={() => {
            // Filtra el listado por "sin categoría" (el backend ya soporta
            // `uncategorized=true`). Limpiamos el resto de filtros para que
            // lo mostrado coincida con el conteo del banner, que es global
            // (todas las sin categoría del usuario, no las del mes/cuenta).
            setFilters({ limit: PAGE_SIZE, offset: 0, uncategorized: true });
          }}
        />

        {/* PHASE-41 — data-hygiene de dirección de transferencias, movida
            aquí desde la retirada pestaña /transfers. Sólo se pinta si hay
            tx mal direccionadas. */}
        <MisclassifiedSection />

        {/* PHASE-46 — abonos que el banco te hace al aplazar un recibo: entran
            como ingreso y no lo son. Se propone atarlos a la deuda cuyo cuadro
            tiene ese mismo capital. Sólo se pinta si hay alguno. */}
        <FinancingMatchesSection />

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
              {/* Plegada por defecto, como el panel de Filtros. Antes estaba
                  siempre desplegada y su desplegable de cuentas —sin etiqueta
                  visible, sólo `aria-label`— se leía como el filtro de cuenta,
                  que en cambio vive dentro de «Filtros». Dos desplegables
                  idénticos, y el que hacía lo obvio era el escondido. */}
              <Button
                variant="ghost"
                onClick={() => setBulkOpen((v) => !v)}
                aria-expanded={bulkOpen}
              >
                {bulkOpen ? 'Ocultar acciones en bloque' : 'Acciones en bloque'}
              </Button>
            </div>
            {bulkOpen ? (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'flex-end',
                  gap: spacing.sm,
                  flexWrap: 'wrap',
                  backgroundColor: colors.surfaceMuted,
                  border: `1px solid ${colors.border}`,
                  borderRadius: radius.md,
                  padding: spacing.md,
                }}
              >
                <span style={{ fontSize: fontSize.xs, color: colors.textMuted, marginRight: 'auto' }}>
                  Actúan sobre las {total}{' '}
                  {total === 1 ? 'transacción' : 'transacciones'} que ves ahora, no
                  sólo sobre esta página.
                </span>
                {/* PHASE-32 — reasignar en bloque a una cuenta (consolidar el
                    mes en tu cuenta principal). Usa los filtros activos. */}
                {activeAccounts.length > 0 ? (
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: spacing.xs }}>
                    {/* Etiqueta VISIBLE: un `aria-label` no lo lee quien mira la
                        pantalla, y sin ella este desplegable era indistinguible
                        del filtro de cuenta. */}
                    <label
                      htmlFor="reassign-target"
                      style={{ fontSize: fontSize.xs, color: colors.textMuted }}
                    >
                      Mover a:
                    </label>
                    <select
                      id="reassign-target"
                      value={reassignTarget}
                      onChange={(e) => setReassignTargetId(e.target.value)}
                      aria-label="Cuenta destino para reasignar"
                      style={{
                        padding: `${spacing.xs}px ${spacing.sm}px`,
                        borderRadius: radius.sm,
                        border: `1px solid ${colors.border}`,
                        backgroundColor: colors.surface,
                        color: colors.text,
                        fontSize: fontSize.sm,
                      }}
                    >
                      {activeAccounts.map((a) => (
                        <option key={a.id} value={a.id}>
                          {a.icon ? `${a.icon} ` : ''}
                          {a.name}
                          {a.is_default ? ' (principal)' : ''}
                        </option>
                      ))}
                    </select>
                    <Button
                      variant="secondary"
                      onClick={() => setConfirmingReassign(true)}
                      disabled={
                        total === 0 ||
                        !reassignTarget ||
                        reassignMutation.isPending ||
                        bulkDisabledByUncategorized
                      }
                      title={
                        bulkDisabledByUncategorized
                          ? "No disponible con el filtro 'sin categoría'"
                          : undefined
                      }
                    >
                      {reassignMutation.isPending ? 'Moviendo…' : 'Mover a la cuenta'}
                    </Button>
                  </span>
                ) : null}
                <Button
                  variant="ghost"
                  onClick={() => setConfirmingBulkDelete(true)}
                  disabled={
                    total === 0 || bulkDeleteMutation.isPending || bulkDisabledByUncategorized
                  }
                  title={
                    bulkDisabledByUncategorized
                      ? "No disponible con el filtro 'sin categoría'"
                      : undefined
                  }
                  style={{ color: colors.danger, borderColor: colors.danger }}
                >
                  {bulkDeleteMutation.isPending ? 'Borrando…' : 'Borrar todo'}
                </Button>
              </div>
            ) : null}

            {/* PHASE-34 — barra de selección: aparece al marcar checkboxes y
                permite recategorizar TODAS las marcadas de una vez. */}
            {selectedIds.size > 0 ? (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: spacing.sm,
                  flexWrap: 'wrap',
                  padding: `${spacing.sm}px ${spacing.md}px`,
                  backgroundColor: colors.primarySoft,
                  border: `1px solid ${colors.primary}`,
                  borderRadius: radius.md,
                }}
              >
                <span
                  style={{
                    fontSize: fontSize.sm,
                    fontWeight: fontWeight.semibold,
                    color: colors.text,
                  }}
                >
                  {selectedIds.size}{' '}
                  {selectedIds.size === 1 ? 'seleccionada' : 'seleccionadas'}
                </span>
                <span style={{ flex: 1 }} />
                <select
                  value={bulkCategoryId}
                  onChange={(e) => setBulkCategoryId(e.target.value)}
                  aria-label="Categoría para aplicar en bloque"
                  style={{
                    padding: `${spacing.xs}px ${spacing.sm}px`,
                    borderRadius: radius.sm,
                    border: `1px solid ${colors.border}`,
                    backgroundColor: colors.surface,
                    color: colors.text,
                    fontSize: fontSize.sm,
                  }}
                >
                  <option value="">Cambiar categoría a…</option>
                  {bulkCategoryOptions.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.icon ? `${c.icon} ` : ''}
                      {c.name}
                    </option>
                  ))}
                </select>
                <Button
                  variant="secondary"
                  onClick={applyBulkCategory}
                  disabled={!bulkCategoryId || bulkCategorizeMutation.isPending}
                >
                  {bulkCategorizeMutation.isPending ? 'Aplicando…' : 'Cambiar categoría'}
                </Button>
                <Button
                  variant="ghost"
                  onClick={() => {
                    setSelectedIds(new Set());
                    setBulkCategoryId('');
                  }}
                >
                  Quitar selección
                </Button>
              </div>
            ) : null}

            <TransactionList
              items={items}
              categories={categories ?? []}
              onDelete={handleDelete}
              onUnlinkTransfer={handleUnlinkTransfer}
              deletingId={deleteMutation.isPending ? (deleteMutation.variables ?? null) : null}
              unlinkingId={
                unlinkTransferMutation.isPending ? (unlinkTransferMutation.variables ?? null) : null
              }
              selectedIds={selectedIds}
              onToggleSelect={toggleSelect}
              onToggleSelectAll={toggleSelectAll}
              allSelected={allSelected}
              someSelected={someSelected}
              deferredLiabilityName={deferredLiabilityName}
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

      <ConfirmDialog
        open={confirmingReassign}
        title={
          hasActiveFilters
            ? `¿Mover las transacciones filtradas a "${reassignTargetName}"?`
            : `¿Mover TODAS tus transacciones activas a "${reassignTargetName}"?`
        }
        description={
          // AUDIT LOW#12 — no prometemos un número exacto: el backend
          // excluye transferencias internas, las ya en destino y las de otra
          // divisa, así que el `total` del listado sobreestimaba lo que se
          // mueve. El toast posterior informa cuántas se movieron y omitieron.
          (hasActiveFilters
            ? 'Se moverán las que coinciden con los filtros activos. '
            : 'Se reasignarán todas tus transacciones activas. ') +
          'Se excluyen las transferencias internas, las que ya están en esa cuenta y las de otra divisa. El saldo de la cuenta destino reflejará estos movimientos.'
        }
        confirmLabel="Mover a la cuenta"
        tone="primary"
        loading={reassignMutation.isPending}
        onConfirm={confirmReassign}
        onCancel={() => setConfirmingReassign(false)}
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
  const offset = Number.isFinite(parsedOffset) && parsedOffset > 0 ? Math.floor(parsedOffset) : 0;
  const accountId = searchParams.get('account_id');
  const categoryId = searchParams.get('category_id');
  const uncategorized = searchParams.get('uncategorized') === '1';
  const dateFrom = searchParams.get('date_from');
  const dateTo = searchParams.get('date_to');
  const search = searchParams.get('search');
  return {
    limit: PAGE_SIZE,
    offset,
    ...(accountId ? { account_id: accountId } : {}),
    // `uncategorized` es excluyente con `category_id`: si ambos vienen en
    // la URL (no debería), gana "sin categoría".
    ...(uncategorized
      ? { uncategorized: true }
      : categoryId
        ? { category_id: categoryId }
        : {}),
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
  if (filters.uncategorized) sp.set('uncategorized', '1');
  else if (filters.category_id) sp.set('category_id', filters.category_id);
  if (filters.date_from) sp.set('date_from', filters.date_from);
  if (filters.date_to) sp.set('date_to', filters.date_to);
  if (filters.search) sp.set('search', filters.search);
  return sp;
}
