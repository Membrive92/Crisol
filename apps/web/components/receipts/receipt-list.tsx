'use client';

import Link from 'next/link';

import type { Receipt } from '@finanzas/types';
import { colors, fontSize, fontWeight, formatDate, radius, spacing } from '@finanzas/ui';

import { ReceiptStatusBadge } from './status-badge';

export interface ReceiptListProps {
  items: Receipt[];
}

export function ReceiptList({ items }: ReceiptListProps) {
  if (items.length === 0) {
    return (
      <div
        style={{
          padding: spacing.xl,
          textAlign: 'center',
          color: colors.textMuted,
          backgroundColor: colors.surfaceMuted,
          borderRadius: radius.md,
        }}
      >
        Aún no has subido tickets.
      </div>
    );
  }

  return (
    <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
      {items.map((r) => {
        const merchant = pickMerchant(r);
        const total = pickTotal(r);
        return (
          <li
            key={r.id}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: spacing.md,
              padding: spacing.md,
              borderBottom: `1px solid ${colors.border}`,
            }}
          >
            <div style={{ flex: 1, minWidth: 0 }}>
              <div
                style={{
                  fontSize: fontSize.md,
                  fontWeight: fontWeight.medium,
                  color: colors.text,
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                {merchant ?? '(sin comercio)'}
              </div>
              <div style={{ fontSize: fontSize.sm, color: colors.textMuted }}>
                {formatDate(r.created_at)} · {total ?? '—'}
              </div>
            </div>
            <ReceiptStatusBadge status={r.status} />
            <Link
              href={{ pathname: `/personal-finance/receipts/${r.id}` }}
              style={{
                fontSize: fontSize.sm,
                fontWeight: fontWeight.medium,
                color: colors.primary,
                textDecoration: 'none',
              }}
            >
              Ver →
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

function pickMerchant(r: Receipt): string | null {
  const ext = r.extraction as Record<string, unknown>;
  const merchant = ext['merchant'];
  return typeof merchant === 'string' ? merchant : null;
}

function pickTotal(r: Receipt): string | null {
  const ext = r.extraction as Record<string, unknown>;
  const total = ext['total'];
  const currency = ext['currency'] ?? 'EUR';
  if (typeof total !== 'string') return null;
  return `${total} ${typeof currency === 'string' ? currency : ''}`.trim();
}
