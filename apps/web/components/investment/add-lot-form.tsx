'use client';

import { useState } from 'react';

import { formatApiError, useCreateLot } from '@crisol/services';
import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';

import { SecuritySearch } from './security-search';

function todayIso(): string {
  // Sin `new Date()` en módulos; aquí (cliente, evento) es seguro.
  return new Date().toISOString().slice(0, 10);
}

const inputStyle: React.CSSProperties = {
  padding: `${spacing.sm}px ${spacing.md}px`,
  borderRadius: radius.md,
  border: `1px solid ${colors.border}`,
  backgroundColor: colors.surface,
  color: colors.text,
  fontSize: fontSize.sm,
};

/** Alta de un lote (compra). Elige el valor, cantidad, precio y fecha. */
export function AddLotForm({ onDone }: { onDone: () => void }) {
  const [securityId, setSecurityId] = useState<string | null>(null);
  const [quantity, setQuantity] = useState('');
  const [price, setPrice] = useState('');
  const [tradeDate, setTradeDate] = useState(todayIso());
  const createLot = useCreateLot();

  async function submit(): Promise<void> {
    if (!securityId || !quantity || !price) return;
    await createLot.mutateAsync({
      security_id: securityId,
      trade_date: tradeDate,
      quantity,
      price,
    });
    setSecurityId(null);
    setQuantity('');
    setPrice('');
    onDone();
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.md }}>
      {securityId ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: spacing.sm }}>
          <span style={{ color: colors.success, fontSize: fontSize.sm, fontWeight: fontWeight.semibold }}>
            Valor elegido ✓
          </span>
          <button
            type="button"
            onClick={() => setSecurityId(null)}
            style={{ background: 'none', border: 'none', color: colors.primary, cursor: 'pointer', fontSize: fontSize.sm }}
          >
            cambiar
          </button>
        </div>
      ) : (
        <SecuritySearch onSelect={setSecurityId} placeholder="Valor de la compra" />
      )}

      <div style={{ display: 'flex', gap: spacing.sm, flexWrap: 'wrap' }}>
        <input
          type="number"
          value={quantity}
          onChange={(e) => setQuantity(e.target.value)}
          placeholder="Cantidad"
          style={{ ...inputStyle, width: 120 }}
        />
        <input
          type="number"
          value={price}
          onChange={(e) => setPrice(e.target.value)}
          placeholder="Precio"
          style={{ ...inputStyle, width: 120 }}
        />
        <input
          type="date"
          value={tradeDate}
          onChange={(e) => setTradeDate(e.target.value)}
          style={inputStyle}
        />
        <button
          type="button"
          onClick={() => void submit()}
          disabled={!securityId || !quantity || !price || createLot.isPending}
          style={{
            backgroundColor: colors.primary,
            color: colors.onPrimary,
            border: 'none',
            borderRadius: radius.md,
            padding: `${spacing.sm}px ${spacing.lg}px`,
            fontSize: fontSize.sm,
            fontWeight: 600,
            cursor: 'pointer',
            opacity: !securityId || !quantity || !price ? 0.6 : 1,
          }}
        >
          {createLot.isPending ? 'Añadiendo…' : 'Añadir compra'}
        </button>
      </div>
      {createLot.isError ? (
        <span style={{ color: colors.danger, fontSize: fontSize.sm }}>
          {formatApiError(createLot.error, 'No se pudo añadir la compra.')}
        </span>
      ) : null}
    </div>
  );
}
