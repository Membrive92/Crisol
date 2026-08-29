'use client';

import type { ReactNode } from 'react';

import { colors, fontSize, fontWeight, radius, spacing, layout } from '@crisol/ui';

export interface DegradedPanelProps {
  title: string;
  /** Por qué no hay contenido. En español y accionable, o explícitamente «no
   *  es reparable». */
  reason: string;
  /** Qué consecuencia tiene sobre el resto del informe. */
  consequence?: string | undefined;
  children?: ReactNode;
}

/**
 * Estado degradado de primera clase.
 *
 * Hay nueve situaciones en las que una parte del informe no se puede calcular y
 * NO es un fallo: una financiera no admite los modelos forenses, un balance no
 * clasificado no da liquidez, una serie de un año no da variaciones. Pintar una
 * pestaña vacía en esos casos hace que el usuario reingiera una y otra vez
 * buscando arreglar algo que no está roto.
 */
export function DegradedPanel({ title, reason, consequence, children }: DegradedPanelProps) {
  return (
    <div
      style={{
        borderRadius: radius.md,
        border: `1px dashed ${colors.border}`,
        backgroundColor: colors.surfaceMuted,
        padding: spacing.lg,
        display: 'flex',
        flexDirection: 'column',
        gap: spacing.sm,
      }}
    >
      <p
        style={{
          margin: 0,
          color: colors.text,
          fontSize: fontSize.md,
          fontWeight: fontWeight.semibold,
        }}
      >
        {title}
      </p>
      <p
        style={{
          margin: 0,
          maxWidth: layout.prose,
          color: colors.textMuted,
          fontSize: fontSize.sm,
          lineHeight: 1.5,
        }}
      >
        {reason}
      </p>
      {consequence ? (
        <p
          style={{
            margin: 0,
            maxWidth: layout.prose,
            color: colors.textSubtle,
            fontSize: fontSize.xs,
            lineHeight: 1.5,
          }}
        >
          {consequence}
        </p>
      ) : null}
      {children}
    </div>
  );
}

/**
 * Aviso en línea, para cabeceras de sección (avisos de cuadre, convenciones).
 *
 * Acotado a `layout.prose` y alineado al inicio: es el bloque de prosa que
 * encabeza CADA pestaña del informe, y sin el límite era una banda gris de
 * borde a borde con dos líneas de 2.000 px.
 */
export function InlineNotice({ children }: { children: ReactNode }) {
  return (
    <p
      style={{
        margin: 0,
        maxWidth: layout.prose,
        alignSelf: 'flex-start',
        color: colors.textMuted,
        fontSize: fontSize.xs,
        lineHeight: 1.5,
        backgroundColor: colors.surfaceMuted,
        borderRadius: radius.sm,
        padding: `${spacing.sm}px ${spacing.md}px`,
      }}
    >
      {children}
    </p>
  );
}
