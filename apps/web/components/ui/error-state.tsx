'use client';

import { colors, fontSize, fontWeight, spacing } from '@crisol/ui';

import { Button } from './button';
import { Card } from './card';

export interface ErrorStateProps {
  /** Título corto del error. Default genérico. */
  title?: string;
  /** Mensaje explicativo. Default genérico accionable. */
  description?: string;
  /**
   * Handler de reintento. Típicamente `query.refetch`. Si se omite no
   * se pinta el botón (p. ej. cuando el error no es recuperable in-situ).
   */
  onRetry?: (() => void) | undefined;
  /** Etiqueta del botón de reintento. Default "Reintentar". */
  retryLabel?: string;
  /** Indica que el reintento está en curso (deshabilita el botón). */
  retrying?: boolean;
  /** Variante compacta para incrustar dentro de una sección. */
  compact?: boolean;
}

/**
 * Estado de error reutilizable para ramas `isError` de las queries.
 *
 * Antes de AUDIT-2026-05 las páginas trataban el error como "lista
 * vacía" (mostraban el empty-state), ocultando fallos de red / 5xx al
 * usuario sin ninguna vía de recuperación. Este componente da un
 * mensaje claro + un botón "Reintentar" cableado al `refetch` de la
 * query, sin recargar la página entera.
 */
export function ErrorState({
  title = 'No se pudieron cargar los datos',
  description = 'Ha ocurrido un problema al contactar con el servidor. Comprueba tu conexión e inténtalo de nuevo.',
  onRetry,
  retryLabel = 'Reintentar',
  retrying = false,
  compact = false,
}: ErrorStateProps) {
  return (
    <Card
      role="alert"
      style={{
        padding: compact ? spacing.md : spacing.lg,
        textAlign: 'center',
        backgroundColor: colors.dangerSoft,
        border: `1px solid ${colors.danger}`,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: spacing.sm,
      }}
    >
      <p
        style={{
          margin: 0,
          fontSize: fontSize.md,
          fontWeight: fontWeight.semibold,
          color: colors.text,
        }}
      >
        {title}
      </p>
      <p
        style={{
          margin: 0,
          fontSize: fontSize.sm,
          color: colors.textMuted,
          lineHeight: 1.4,
          maxWidth: 420,
        }}
      >
        {description}
      </p>
      {onRetry ? (
        <Button
          variant="secondary"
          onClick={onRetry}
          disabled={retrying}
          style={{ marginTop: spacing.xs }}
        >
          {retrying ? 'Reintentando…' : retryLabel}
        </Button>
      ) : null}
    </Card>
  );
}
