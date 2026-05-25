'use client';

import {
  formatApiError,
  useAccounts,
  useLinkTransfer,
  useMarkTransfer,
  useMatchTransfers,
  useTransferCandidates,
  useTransferSuspects,
  useTransfers,
  useUnlinkTransfer,
} from '@crisol/services';
import { toast } from '@crisol/store';
import {
  colors,
  fontSize,
  fontWeight,
  formatAmount,
  formatDate,
  radius,
  spacing,
} from '@crisol/ui';
import type { Account, TransferSuspect } from '@crisol/types';

import { MisclassifiedSection } from '@/components/transfers/misclassified-section';
import { TransferPairCard } from '@/components/transfers/transfer-pair-card';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';

export default function TransfersPage() {
  const transfersQuery = useTransfers();
  const candidatesQuery = useTransferCandidates(3);
  const suspectsQuery = useTransferSuspects();
  // includeArchived: las cuentas archivadas pueden formar parte de
  // pares históricos — necesitamos su nombre/color para resolver el
  // display, aunque ya no aparezcan en selectors.
  const accountsQuery = useAccounts({ includeArchived: true });

  const matchMutation = useMatchTransfers();
  const linkMutation = useLinkTransfer();
  const unlinkMutation = useUnlinkTransfer();
  const markMutation = useMarkTransfer();

  const pairs = transfersQuery.data ?? [];
  const candidates = candidatesQuery.data ?? [];
  const suspects = suspectsQuery.data ?? [];
  const accounts = accountsQuery.data ?? [];

  function handleAutoMatch() {
    matchMutation.mutate(undefined, {
      onSuccess: (response) => {
        const linked = response.linked_count;
        const pending = response.pending_candidates.length;
        if (linked === 0 && pending === 0) {
          toast.info('No se han encontrado nuevas transferencias.');
          return;
        }
        const parts: string[] = [];
        if (linked > 0) {
          parts.push(
            `${linked} ${linked === 1 ? 'par enlazado' : 'pares enlazados'}`,
          );
        }
        if (pending > 0) {
          parts.push(
            `${pending} ${
              pending === 1 ? 'candidato ambiguo' : 'candidatos ambiguos'
            } esperando confirmación`,
          );
        }
        toast.success(parts.join(' · '));
      },
      onError: (err) =>
        toast.error(formatApiError(err, 'Error al detectar transferencias.')),
    });
  }

  function handleLink(outId: string, inId: string) {
    linkMutation.mutate(
      { out_transaction_id: outId, in_transaction_id: inId },
      {
        onSuccess: () => toast.success('Par enlazado.'),
        onError: (err) => toast.error(formatApiError(err, 'Error al enlazar.')),
      },
    );
  }

  function handleUnlink(outId: string) {
    unlinkMutation.mutate(outId, {
      onSuccess: () => toast.info('Par deshecho.'),
      onError: (err) => toast.error(formatApiError(err, 'Error al deshacer.')),
    });
  }

  function handleMark(transactionId: string) {
    markMutation.mutate(
      { transaction_id: transactionId },
      {
        onSuccess: (response) =>
          toast.success(`Marcada como "${response.category_name}".`),
        onError: (err) =>
          toast.error(formatApiError(err, 'No se pudo marcar.')),
      },
    );
  }

  // Sólo mostramos la sección "Sugerencias" si hay candidatos
  // pendientes — si la lista está vacía y no hay pares, esconder
  // la sección entera evita ruido en la primera carga.
  const showSuggestions = candidates.length > 0;

  return (
    <div style={{ maxWidth: 960, margin: '0 auto', padding: spacing.lg }}>
      <header
        style={{
          display: 'flex',
          alignItems: 'flex-end',
          justifyContent: 'space-between',
          gap: spacing.md,
          flexWrap: 'wrap',
          marginBottom: spacing.xl,
        }}
      >
        <div style={{ flex: '1 1 360px' }}>
          <h1
            style={{
              margin: 0,
              fontSize: fontSize.xxl,
              fontWeight: fontWeight.bold,
              color: colors.text,
              letterSpacing: '-0.02em',
              lineHeight: 1.1,
            }}
          >
            Transferencias internas
          </h1>
          <p
            style={{
              margin: `${spacing.xs}px 0 0 0`,
              color: colors.textMuted,
              fontSize: fontSize.sm,
              lineHeight: 1.4,
            }}
          >
            Cuando muevas dinero entre tus propias cuentas, enlaza la
            salida y la entrada para que no cuenten como gasto/ingreso
            real. Sí afectan al saldo de cada cuenta, pero quedan fuera
            del cashflow, la tasa de ahorro y los presupuestos.
          </p>
        </div>
        <Button
          onClick={handleAutoMatch}
          disabled={matchMutation.isPending}
          variant="secondary"
        >
          {matchMutation.isPending ? 'Detectando…' : 'Detectar automáticas'}
        </Button>
      </header>

      {/* PHASE-31.2 — sección bulk-fix arriba del todo: si hay tx mal
          direccionadas el saldo está afectado y conviene resolverlo
          antes de tocar pares sueltos. */}
      <div style={{ marginBottom: spacing.xl }}>
        <MisclassifiedSection />
      </div>

      {suspects.length > 0 ? (
        <section style={{ marginBottom: spacing.xl }}>
          <h2 style={sectionHeaderStyle}>Sospechosas</h2>
          <p
            style={{
              margin: `0 0 ${spacing.md}px 0`,
              fontSize: fontSize.xs,
              color: colors.textMuted,
              lineHeight: 1.4,
            }}
          >
            Estas transacciones llevan "transfer" en la descripción y no
            tienen pareja detectada — habituales cuando sólo importas el
            extracto de una de tus cuentas. Marca como transferencia las
            que muevan dinero entre tus propias cuentas para sacarlas
            del cashflow.
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.sm }}>
            {suspects.map((s) => {
              const busy =
                markMutation.isPending &&
                markMutation.variables?.transaction_id === s.transaction_id;
              return (
                <SuspectCard
                  key={s.transaction_id}
                  suspect={s}
                  accounts={accounts}
                  busy={busy}
                  onMark={() => handleMark(s.transaction_id)}
                />
              );
            })}
          </div>
        </section>
      ) : null}

      <section style={{ marginBottom: spacing.xl }}>
        <h2 style={sectionHeaderStyle}>Pares activos</h2>
        {transfersQuery.isLoading ? (
          <p style={{ color: colors.textMuted }}>Cargando…</p>
        ) : pairs.length === 0 ? (
          <Card
            style={{
              padding: spacing.lg,
              textAlign: 'center',
              backgroundColor: colors.surfaceMuted,
              border: `1px dashed ${colors.border}`,
            }}
          >
            <p style={{ margin: 0, color: colors.textMuted, fontSize: fontSize.sm }}>
              Aún no hay pares enlazados. Pulsa "Detectar automáticas"
              para que el detector busque candidatos en tus
              transacciones.
            </p>
          </Card>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.sm }}>
            {pairs.map((pair) => {
              const busy =
                unlinkMutation.isPending &&
                unlinkMutation.variables === pair.out_transaction_id;
              return (
                <TransferPairCard
                  key={`${pair.out_transaction_id}-${pair.in_transaction_id}`}
                  pair={pair}
                  accounts={accounts}
                  primaryAction={{
                    label: 'Deshacer',
                    onClick: () => handleUnlink(pair.out_transaction_id),
                    variant: 'ghost',
                    busy,
                  }}
                />
              );
            })}
          </div>
        )}
      </section>

      {showSuggestions ? (
        <section>
          <h2 style={sectionHeaderStyle}>Sugerencias pendientes</h2>
          <p
            style={{
              margin: `0 0 ${spacing.md}px 0`,
              fontSize: fontSize.xs,
              color: colors.textMuted,
              lineHeight: 1.4,
            }}
          >
            Estas parejas tienen el mismo importe y fechas próximas
            pero el matcher no las enlazó automáticamente (suelen ser
            ambiguas porque hay varios candidatos coincidentes).
            Confírmalas una a una.
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.sm }}>
            {candidates.map((candidate) => {
              const variables = linkMutation.variables;
              const busy =
                linkMutation.isPending &&
                variables?.out_transaction_id === candidate.out_transaction_id &&
                variables?.in_transaction_id === candidate.in_transaction_id;
              return (
                <TransferPairCard
                  key={`${candidate.out_transaction_id}-${candidate.in_transaction_id}`}
                  pair={candidate}
                  accounts={accounts}
                  primaryAction={{
                    label: 'Enlazar',
                    onClick: () =>
                      handleLink(
                        candidate.out_transaction_id,
                        candidate.in_transaction_id,
                      ),
                    variant: 'primary',
                    busy,
                  }}
                />
              );
            })}
          </div>
        </section>
      ) : null}
    </div>
  );
}

const sectionHeaderStyle: React.CSSProperties = {
  fontSize: fontSize.lg,
  fontWeight: fontWeight.semibold,
  color: colors.text,
  marginTop: 0,
  marginBottom: spacing.md,
};

interface SuspectCardProps {
  suspect: TransferSuspect;
  accounts: Account[];
  busy: boolean;
  onMark: () => void;
}

function SuspectCard({ suspect, accounts, busy, onMark }: SuspectCardProps) {
  const account = accounts.find((a) => a.id === suspect.account_id);
  const accountLabel = account?.name ?? 'Cuenta desconocida';
  return (
    <Card
      style={{
        padding: spacing.md,
        display: 'flex',
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: spacing.md,
        flexWrap: 'wrap',
        borderRadius: radius.md,
      }}
    >
      <div style={{ flex: '1 1 320px', minWidth: 0 }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'baseline',
            gap: spacing.sm,
            flexWrap: 'wrap',
          }}
        >
          <span
            style={{
              fontSize: fontSize.md,
              fontWeight: fontWeight.semibold,
              color: colors.text,
            }}
          >
            {formatAmount(suspect.amount, suspect.currency)}
          </span>
          <span style={{ fontSize: fontSize.xs, color: colors.textMuted }}>
            {accountLabel} · {formatDate(suspect.occurred_at)}
          </span>
        </div>
        <p
          style={{
            margin: `${spacing.xs}px 0 0 0`,
            fontSize: fontSize.sm,
            color: colors.textMuted,
            lineHeight: 1.4,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
          title={suspect.description ?? ''}
        >
          {suspect.description ?? '—'}
        </p>
        {suspect.current_category_name ? (
          <p
            style={{
              margin: `${spacing.xs / 2}px 0 0 0`,
              fontSize: fontSize.xs,
              color: colors.textSubtle,
            }}
          >
            Categoría actual: {suspect.current_category_name}
          </p>
        ) : null}
      </div>
      <Button onClick={onMark} disabled={busy} variant="secondary">
        {busy ? 'Marcando…' : 'Marcar como transferencia'}
      </Button>
    </Card>
  );
}
