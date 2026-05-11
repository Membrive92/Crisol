'use client';

import {
  formatApiError,
  useAccounts,
  useLinkTransfer,
  useMatchTransfers,
  useTransferCandidates,
  useTransfers,
  useUnlinkTransfer,
} from '@crisol/services';
import { toast } from '@crisol/store';
import { colors, fontSize, fontWeight, spacing } from '@crisol/ui';

import { TransferPairCard } from '@/components/transfers/transfer-pair-card';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';

export default function TransfersPage() {
  const transfersQuery = useTransfers();
  const candidatesQuery = useTransferCandidates(3);
  // includeArchived: las cuentas archivadas pueden formar parte de
  // pares históricos — necesitamos su nombre/color para resolver el
  // display, aunque ya no aparezcan en selectors.
  const accountsQuery = useAccounts({ includeArchived: true });

  const matchMutation = useMatchTransfers();
  const linkMutation = useLinkTransfer();
  const unlinkMutation = useUnlinkTransfer();

  const pairs = transfersQuery.data ?? [];
  const candidates = candidatesQuery.data ?? [];
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
