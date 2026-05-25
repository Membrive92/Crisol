'use client';

import { useUncategorizedSummary } from '@crisol/services';
import {
  colors,
  fontSize,
  fontWeight,
  formatAmount,
  radius,
  spacing,
} from '@crisol/ui';

import { Button } from '@/components/ui/button';
import { InfoIcon } from '@/components/ui/icons';

export interface UncategorizedBannerProps {
  /**
   * Acción que aplica el filtro "sin categoría" en el listado. Si no
   * se pasa, el banner sigue siendo informativo y el usuario navega a
   * mano. El call-site típico (transactions/page) sí lo pasa.
   */
  onSeeUncategorized?: () => void;
}

/**
 * PHASE-31.3 — Banner que aparece encima de la tabla de transacciones
 * cuando hay tx sin categoría. Tras 31.3 estas tx YA no contaminan el
 * saldo (`else_=0` en el cómputo), así que conviene que el usuario las
 * vea explícitamente para no perderlas de vista (antes pasaban
 * desapercibidas porque "sumaban a algún sitio").
 *
 * Si no hay tx sin categoría, el banner no se renderiza.
 */
export function UncategorizedBanner({ onSeeUncategorized }: UncategorizedBannerProps) {
  const { data } = useUncategorizedSummary();
  if (!data || data.count === 0) return null;

  return (
    <div
      role="status"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: spacing.sm,
        padding: `${spacing.sm}px ${spacing.md}px`,
        backgroundColor: colors.warningSoft,
        border: `1px solid ${colors.warning}`,
        borderRadius: radius.md,
        color: colors.warning,
        fontSize: fontSize.sm,
        lineHeight: 1.4,
      }}
    >
      <InfoIcon size={16} style={{ flex: '0 0 auto' }} />
      <span style={{ flex: 1, minWidth: 0, color: colors.text }}>
        Tienes{' '}
        <strong>
          {data.count} {data.count === 1 ? 'transacción' : 'transacciones'} sin
          categorizar
        </strong>{' '}
        ({formatAmount(data.total_amount, data.currency)} en total). No afectan
        a tu saldo hasta que les asignes una categoría.
      </span>
      {onSeeUncategorized ? (
        <Button
          type="button"
          variant="ghost"
          onClick={onSeeUncategorized}
          style={{ flex: '0 0 auto', fontWeight: fontWeight.semibold }}
        >
          Ver y categorizar
        </Button>
      ) : null}
    </div>
  );
}
