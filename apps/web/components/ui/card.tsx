'use client';

import type { HTMLAttributes } from 'react';

import { colors, radius, spacing } from '@crisol/ui';

export function Card({ style, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      {...rest}
      style={{
        backgroundColor: colors.surface,
        border: `1px solid ${colors.border}`,
        borderRadius: radius.md,
        padding: spacing.md,
        ...style,
      }}
    />
  );
}
