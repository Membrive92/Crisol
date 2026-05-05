'use client';

import { useState } from 'react';

import {
  formatApiError,
  useCategories,
  useConfirmSubscription,
  useDeleteSubscription,
  useDismissSubscription,
  useScanSubscriptions,
  useSubscriptions,
} from '@finanzas/services';
import { toast } from '@finanzas/store';
import { colors, fontSize, fontWeight, spacing } from '@finanzas/ui';

import { SubscriptionCard } from '@/components/subscriptions/subscription-card';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';

export default function SubscriptionsPage() {
  const { data: categories } = useCategories();
  const pendingQuery = useSubscriptions({ status: 'pending' });
  const confirmedQuery = useSubscriptions({ status: 'confirmed' });
  const dismissedQuery = useSubscriptions({ status: 'dismissed' });
  const scanMutation = useScanSubscriptions();
  const confirmMutation = useConfirmSubscription();
  const dismissMutation = useDismissSubscription();
  const deleteMutation = useDeleteSubscription();
  const [showDismissed, setShowDismissed] = useState(false);

  const pending = pendingQuery.data ?? [];
  const confirmed = confirmedQuery.data ?? [];
  const dismissed = dismissedQuery.data ?? [];

  function handleScan() {
    scanMutation.mutate(undefined, {
      onSuccess: (res) =>
        toast.success(
          `Re-escaneado: ${res.created} nuevas, ${res.updated} actualizadas.`,
        ),
      onError: (err) => toast.error(formatApiError(err, 'Error al re-escanear.')),
    });
  }

  function handleConfirm(id: string) {
    confirmMutation.mutate(id, {
      onSuccess: () => toast.success('Subscripción confirmada.'),
      onError: (err) => toast.error(formatApiError(err, 'Error al confirmar.')),
    });
  }

  /** Reactiva una dismissed → confirmed (PHASE-13.1: el confirm de
   * una dismissed la reactiva). */
  function handleReactivate(id: string) {
    confirmMutation.mutate(id, {
      onSuccess: () => toast.success('Subscripción reactivada.'),
      onError: (err) => toast.error(formatApiError(err, 'Error al reactivar.')),
    });
  }

  function handleDismiss(id: string) {
    dismissMutation.mutate(id, {
      onSuccess: () => toast.info('Subscripción descartada — no se volverá a sugerir.'),
      onError: (err) => toast.error(formatApiError(err, 'Error al descartar.')),
    });
  }

  function handleDelete(id: string) {
    if (
      !confirm(
        'Eliminar esta subscripción confirmada. Si el patrón persiste, volverá a aparecer como pendiente en el próximo escaneo. ¿Continuar?',
      )
    ) {
      return;
    }
    deleteMutation.mutate(id, {
      onSuccess: () => toast.success('Subscripción eliminada.'),
      onError: (err) => toast.error(formatApiError(err, 'Error al eliminar.')),
    });
  }

  const confirmingId = confirmMutation.isPending
    ? (confirmMutation.variables as string)
    : null;
  const dismissingId = dismissMutation.isPending
    ? (dismissMutation.variables as string)
    : null;
  const deletingId = deleteMutation.isPending
    ? (deleteMutation.variables as string)
    : null;

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
        <div>
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
            Subscripciones
          </h1>
          <p
            style={{
              margin: `${spacing.xs}px 0 0 0`,
              color: colors.textMuted,
              fontSize: fontSize.sm,
            }}
          >
            Detectadas automáticamente a partir de tus transacciones
            recurrentes (heurística local, sin enviar datos fuera del
            equipo). El detector se ejecuta cada noche; pulsa
            "Re-escanear" para forzar la detección ahora.
          </p>
        </div>
        <Button
          onClick={handleScan}
          disabled={scanMutation.isPending}
          variant="secondary"
        >
          {scanMutation.isPending ? 'Escaneando…' : 'Re-escanear'}
        </Button>
      </header>

      <section style={{ marginBottom: spacing.xl }}>
        <h2 style={sectionHeaderStyle}>Sugeridas (revisa y confirma)</h2>
        {pendingQuery.isLoading ? (
          <p style={{ color: colors.textMuted }}>Cargando…</p>
        ) : pending.length === 0 ? (
          <Card
            style={{
              padding: spacing.lg,
              textAlign: 'center',
              backgroundColor: colors.surfaceMuted,
              border: `1px dashed ${colors.border}`,
            }}
          >
            <p style={{ margin: 0, color: colors.textMuted, fontSize: fontSize.sm }}>
              Sin sugerencias pendientes. Cuando el detector encuentre un
              patrón nuevo aparecerá aquí.
            </p>
          </Card>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.sm }}>
            {pending.map((sub) => (
              <SubscriptionCard
                key={sub.id}
                subscription={sub}
                categories={categories ?? []}
                primaryAction={{
                  label: 'Confirmar',
                  onClick: () => handleConfirm(sub.id),
                  busy: confirmingId === sub.id,
                }}
                secondaryAction={{
                  label: 'Descartar',
                  onClick: () => handleDismiss(sub.id),
                  busy: dismissingId === sub.id,
                }}
              />
            ))}
          </div>
        )}
      </section>

      {confirmed.length > 0 ? (
        <section style={{ marginBottom: spacing.xl }}>
          <h2 style={sectionHeaderStyle}>Confirmadas</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.sm }}>
            {confirmed.map((sub) => (
              <SubscriptionCard
                key={sub.id}
                subscription={sub}
                categories={categories ?? []}
                secondaryAction={{
                  label: 'Eliminar',
                  onClick: () => handleDelete(sub.id),
                  busy: deletingId === sub.id,
                  danger: true,
                }}
              />
            ))}
          </div>
        </section>
      ) : null}

      {dismissed.length > 0 ? (
        <section>
          <button
            type="button"
            onClick={() => setShowDismissed((v) => !v)}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              background: 'none',
              border: 'none',
              padding: 0,
              cursor: 'pointer',
              color: colors.textMuted,
              fontSize: fontSize.sm,
              fontWeight: fontWeight.medium,
              marginBottom: showDismissed ? spacing.md : 0,
            }}
            aria-expanded={showDismissed}
          >
            <span aria-hidden style={{ fontSize: fontSize.xs }}>
              {showDismissed ? '▾' : '▸'}
            </span>
            Descartadas ({dismissed.length})
          </button>
          {showDismissed ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.sm }}>
              {dismissed.map((sub) => (
                <SubscriptionCard
                  key={sub.id}
                  subscription={sub}
                  categories={categories ?? []}
                  primaryAction={{
                    label: 'Reactivar',
                    onClick: () => handleReactivate(sub.id),
                    busy: confirmingId === sub.id,
                  }}
                  secondaryAction={{
                    label: 'Eliminar',
                    onClick: () => handleDelete(sub.id),
                    busy: deletingId === sub.id,
                    danger: true,
                  }}
                />
              ))}
            </div>
          ) : null}
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
