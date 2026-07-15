'use client';

import { useEffect, useMemo, useRef, useState } from 'react';

import {
  useAccounts,
  useConvertToDebt,
} from '@crisol/services';
import type {
  NewLiabilityForDebt,
  Transaction,
  TransferPair,
} from '@crisol/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';

import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Select, TextInput } from '@/components/ui/field';

interface Props {
  transaction: Transaction;
  /**
   * P2 (transfers-ux): la heurística de descripción ya no OCULTA el
   * bloque (siempre visible si la tx no está pareada); sólo lo DESTACA
   * con un chip "sugerido" cuando el texto parece una compra financiada.
   */
  suggested?: boolean;
  onConverted: (pair: TransferPair) => void;
  onError: (err: unknown) => void;
}

type Mode = 'existing' | 'new';
type LiabilityType = NewLiabilityForDebt['type'];

const LIABILITY_TYPE_LABEL: Record<LiabilityType, string> = {
  credit_card: 'Tarjeta de crédito',
  loan: 'Préstamo',
  mortgage: 'Hipoteca',
};

/**
 * PHASE-24: bloque "Convertir en operación financiada".
 *
 * Aparece en el detalle de tx cuando la tx no está emparejada y la
 * descripción sugiere una operación financiada (heurística sencilla).
 * Soporta dos modos:
 * - Usar una cuenta de deuda existente.
 * - Crear una nueva al vuelo (con APR/plazo/fecha si es loan/mortgage).
 */
export function ConvertToDebtDialog({
  transaction,
  suggested,
  onConverted,
  onError,
}: Props) {
  const accountsQuery = useAccounts({ includeArchived: false });
  const mutation = useConvertToDebt();

  const liabilities = useMemo(
    () =>
      (accountsQuery.data ?? []).filter(
        (a) =>
          a.nature === 'liability' &&
          a.currency === transaction.currency &&
          !a.is_archived,
      ),
    [accountsQuery.data, transaction.currency],
  );

  // PHASE-35 — tarjetas de crédito (no anidadas) bajo las que se puede
  // registrar la nueva deuda como compra a plazos con su propio cuadro.
  const parentCards = useMemo(
    () =>
      (accountsQuery.data ?? []).filter(
        (a) =>
          a.type === 'credit_card' &&
          a.nature === 'liability' &&
          a.currency === transaction.currency &&
          !a.is_archived &&
          !a.parent_account_id,
      ),
    [accountsQuery.data, transaction.currency],
  );

  // Por defecto: si hay liabilities elegibles, modo "existing"; si no,
  // "new" — el usuario suele estar registrando una nueva deuda.
  const [mode, setMode] = useState<Mode>(
    liabilities.length > 0 ? 'existing' : 'new',
  );
  // AUDIT-2026-07: `liabilities` puede estar vacío en el primer render (las
  // cuentas aún cargan), así que el inicializador caía a 'new' aunque hubiera
  // deudas existentes. Ajustamos a 'existing' una vez cargadas, salvo que el
  // usuario ya haya elegido modo manualmente.
  const modeTouched = useRef(false);
  useEffect(() => {
    if (!modeTouched.current && accountsQuery.isSuccess && liabilities.length > 0) {
      setMode('existing');
    }
  }, [accountsQuery.isSuccess, liabilities.length]);
  const [destinationId, setDestinationId] = useState<string>('');
  // PHASE-24.2: cualquier tipo de deuda acepta plan fijo (incluido
  // credit_card para tarjetas financiadas).
  const [name, setName] = useState<string>('Compra financiada');
  const [type, setType] = useState<LiabilityType>('loan');
  // PHASE-35 — tarjeta padre elegida (compra a plazos anidada). Al elegirla
  // el tipo se fuerza a credit_card y TIN + plazo pasan a obligatorios.
  const [parentCardId, setParentCardId] = useState<string>('');
  const isNestedPurchase = parentCardId !== '';
  const [aprPercent, setAprPercent] = useState<string>('');
  const [taePercent, setTaePercent] = useState<string>('');
  const [termMonths, setTermMonths] = useState<string>('');
  const [totalToPay, setTotalToPay] = useState<string>('');
  const acceptsAmortization = true;

  // PHASE-35 — si la tarjeta seleccionada desaparece del listado (p. ej. se
  // archiva en otra pestaña y la query refresca), limpiamos la selección para
  // no enviar un `parent_account_id` obsoleto que el backend rechazaría.
  useEffect(() => {
    if (parentCardId && !parentCards.some((c) => c.id === parentCardId)) {
      setParentCardId('');
    }
  }, [parentCards, parentCardId]);

  // Validez NUMÉRICA de TIN + plazo (no sólo "no vacío"): el payload descarta
  // valores no finitos, así que el guard debe exigir números reales para no
  // enviar una compra a plazos sin apr/term y comerse un 400 del backend.
  const aprNumericValid = (() => {
    const raw = aprPercent.trim().replace(',', '.');
    return raw !== '' && Number.isFinite(Number(raw));
  })();
  const termNumericValid = (() => {
    const n = Number(termMonths.trim());
    return termMonths.trim() !== '' && Number.isFinite(n) && n > 0;
  })();
  const nestedPlanIncomplete = isNestedPurchase && (!aprNumericValid || !termNumericValid);

  function handleSubmit() {
    if (mode === 'existing') {
      if (!destinationId) return;
      mutation.mutate(
        {
          source_transaction_id: transaction.id,
          destination_account_id: destinationId,
        },
        { onSuccess: onConverted, onError },
      );
      return;
    }
    if (!name.trim()) return;
    // PHASE-35: una compra a plazos anidada exige TIN + plazo NUMÉRICOS (el
    // importe sale de la tx). Guardarraíl en cliente; el backend lo revalida.
    if (nestedPlanIncomplete) return;
    const newLiability: NewLiabilityForDebt = {
      name: name.trim(),
      // Una compra a plazos anidada bajo una tarjeta debe ser credit_card.
      type: isNestedPurchase ? 'credit_card' : type,
      currency: transaction.currency,
    };
    if (isNestedPurchase) newLiability.parent_account_id = parentCardId;
    if (acceptsAmortization) {
      const aprTrimmed = aprPercent.trim().replace(',', '.');
      if (aprTrimmed) {
        const aprNumeric = Number(aprTrimmed);
        if (Number.isFinite(aprNumeric)) {
          newLiability.apr = (aprNumeric / 100).toFixed(4);
        }
      }
      const taeTrimmed = taePercent.trim().replace(',', '.');
      if (taeTrimmed) {
        const taeNumeric = Number(taeTrimmed);
        if (Number.isFinite(taeNumeric)) {
          newLiability.tae = (taeNumeric / 100).toFixed(4);
        }
      }
      const term = termMonths.trim();
      if (term) {
        const n = Number(term);
        if (Number.isFinite(n) && n > 0) newLiability.term_months = n;
      }
      const totalRaw = totalToPay.trim().replace(',', '.');
      if (totalRaw) newLiability.total_to_pay = totalRaw;
      // start_date la decide el backend (= occurred_at de la tx origen).
    }
    mutation.mutate(
      {
        source_transaction_id: transaction.id,
        new_liability: newLiability,
      },
      { onSuccess: onConverted, onError },
    );
  }

  return (
    <Card style={{ padding: spacing.lg, marginTop: spacing.lg }}>
      <h2
        style={{
          margin: 0,
          marginBottom: spacing.xs,
          fontSize: fontSize.lg,
          fontWeight: fontWeight.semibold,
          color: colors.text,
          display: 'flex',
          alignItems: 'center',
          gap: spacing.sm,
        }}
      >
        ¿Es una operación financiada?
        {suggested ? (
          <span
            style={{
              padding: `${spacing.xs / 2}px ${spacing.sm}px`,
              backgroundColor: colors.primarySoft,
              color: colors.primary,
              borderRadius: radius.sm,
              fontSize: fontSize.xs,
              fontWeight: fontWeight.semibold,
              textTransform: 'uppercase',
              letterSpacing: '0.04em',
            }}
          >
            Sugerido
          </span>
        ) : null}
      </h2>
      <p
        style={{
          margin: `0 0 ${spacing.md}px 0`,
          fontSize: fontSize.sm,
          color: colors.textMuted,
          lineHeight: 1.4,
        }}
      >
        Si el banco te abonó este importe como compra a plazos o préstamo,
        regístralo como deuda. Se creará la contraparte en la cuenta de
        deuda y no contará como gasto del mes — pero la deuda crece por{' '}
        {transaction.amount} {transaction.currency} y queda enlazada a esta
        transacción.
      </p>

      <div
        role="tablist"
        style={{
          display: 'inline-flex',
          gap: spacing.xs,
          marginBottom: spacing.md,
        }}
      >
        <ModeTab
          active={mode === 'existing'}
          disabled={liabilities.length === 0}
          onClick={() => {
            modeTouched.current = true;
            setMode('existing');
          }}
          label="Usar deuda existente"
        />
        <ModeTab
          active={mode === 'new'}
          onClick={() => {
            modeTouched.current = true;
            setMode('new');
          }}
          label="Crear nueva"
        />
      </div>

      {mode === 'existing' ? (
        liabilities.length === 0 ? (
          <p
            style={{
              margin: 0,
              fontSize: fontSize.sm,
              color: colors.textSubtle,
              fontStyle: 'italic',
            }}
          >
            No tienes cuentas de deuda en {transaction.currency}. Cambia
            a "Crear nueva" para registrar una.
          </p>
        ) : (
          <div
            style={{
              display: 'flex',
              gap: spacing.sm,
              alignItems: 'flex-end',
              flexWrap: 'wrap',
            }}
          >
            {/* `flex-grow: 0` para que el selector NO se estire a todo el ancho
                de la columna (que ahora es amplia) — se queda en un ancho
                legible y el botón se coloca justo al lado. */}
            <div style={{ flex: '0 1 340px', minWidth: 0 }}>
              <Select
                label="Cuenta de deuda"
                dense
                value={destinationId}
                onChange={(e) => setDestinationId(e.target.value)}
              >
                <option value="">Selecciona una cuenta…</option>
                {liabilities.map((acc) => (
                  <option key={acc.id} value={acc.id}>
                    {acc.name} ({LIABILITY_TYPE_LABEL[acc.type as LiabilityType] ?? acc.type})
                  </option>
                ))}
              </Select>
            </div>
            <Button
              type="button"
              onClick={handleSubmit}
              disabled={!destinationId || mutation.isPending}
            >
              {mutation.isPending ? 'Convirtiendo…' : 'Registrar como deuda'}
            </Button>
          </div>
        )
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.sm }}>
          {parentCards.length > 0 ? (
            <div style={{ flex: '1 1 100%', minWidth: 0 }}>
              <Select
                label="¿Compra a plazos dentro de una tarjeta? (opcional)"
                value={parentCardId}
                onChange={(e) => setParentCardId(e.target.value)}
              >
                <option value="">No — deuda independiente</option>
                {parentCards.map((card) => (
                  <option key={card.id} value={card.id}>
                    Dentro de {card.name}
                  </option>
                ))}
              </Select>
            </div>
          ) : null}
          <div style={{ display: 'flex', gap: spacing.sm, flexWrap: 'wrap' }}>
            <div style={{ flex: '2 1 240px', minWidth: 0 }}>
              <TextInput
                label="Nombre de la cuenta"
                value={name}
                onChange={(e) => setName(e.target.value)}
                maxLength={100}
                placeholder="Tarjeta financiada BBVA"
              />
            </div>
            <div style={{ flex: '1 1 160px', minWidth: 0 }}>
              <Select
                label="Tipo"
                value={isNestedPurchase ? 'credit_card' : type}
                onChange={(e) => setType(e.target.value as LiabilityType)}
                disabled={isNestedPurchase}
              >
                <option value="loan">Préstamo / Compra financiada</option>
                <option value="mortgage">Hipoteca</option>
                <option value="credit_card">Tarjeta (saldo arrastrado)</option>
              </Select>
            </div>
          </div>
          {acceptsAmortization ? (
            <div style={{ display: 'flex', gap: spacing.sm, flexWrap: 'wrap' }}>
              <div style={{ flex: '1 1 120px', minWidth: 0 }}>
                <TextInput
                  label="TIN (%)"
                  value={aprPercent}
                  onChange={(e) => setAprPercent(e.target.value)}
                  placeholder="5,90"
                  inputMode="decimal"
                />
              </div>
              <div style={{ flex: '1 1 120px', minWidth: 0 }}>
                <TextInput
                  label="TAE (%) opc."
                  value={taePercent}
                  onChange={(e) => setTaePercent(e.target.value)}
                  placeholder="6,12"
                  inputMode="decimal"
                />
              </div>
              <div style={{ flex: '1 1 120px', minWidth: 0 }}>
                <TextInput
                  label="Plazo (meses)"
                  value={termMonths}
                  onChange={(e) => setTermMonths(e.target.value)}
                  placeholder="12"
                  inputMode="numeric"
                />
              </div>
              <div style={{ flex: '1 1 160px', minWidth: 0 }}>
                <TextInput
                  label="Total a pagar (€) opc."
                  value={totalToPay}
                  onChange={(e) => setTotalToPay(e.target.value)}
                  placeholder="913,86"
                  inputMode="decimal"
                />
              </div>
            </div>
          ) : null}
          {isNestedPurchase ? (
            <p
              style={{
                margin: 0,
                fontSize: fontSize.xs,
                color: colors.textSubtle,
                lineHeight: 1.4,
              }}
            >
              Se creará como compra a plazos dentro de la tarjeta, con su
              propio cuadro. TIN y plazo son obligatorios; el importe (
              {transaction.amount} {transaction.currency}) se toma de esta
              transacción.
            </p>
          ) : null}
          <Button
            type="button"
            onClick={handleSubmit}
            disabled={!name.trim() || nestedPlanIncomplete || mutation.isPending}
            style={{ alignSelf: 'flex-start' }}
          >
            {mutation.isPending ? 'Creando…' : 'Crear deuda y registrar'}
          </Button>
        </div>
      )}

      {mutation.isError ? (
        <p
          style={{
            marginTop: spacing.sm,
            color: colors.danger,
            fontSize: fontSize.sm,
          }}
        >
          {mutation.error instanceof Error
            ? mutation.error.message
            : 'Error al registrar la deuda'}
        </p>
      ) : null}
      <p
        style={{
          margin: `${spacing.md}px 0 0 0`,
          fontSize: fontSize.xs,
          color: colors.textSubtle,
          borderRadius: radius.sm,
        }}
      >
        La fecha de inicio del cuadro de amortización (si aplica) se
        toma de la fecha de esta transacción. Cross-currency llegará en
        una fase posterior.
      </p>
    </Card>
  );
}

function ModeTab({
  active,
  disabled,
  onClick,
  label,
}: {
  active: boolean;
  disabled?: boolean;
  onClick: () => void;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      style={{
        padding: `${spacing.xs}px ${spacing.sm}px`,
        backgroundColor: active ? colors.primarySoft : 'transparent',
        color: active ? colors.primary : colors.textMuted,
        border: `1px solid ${active ? colors.primary : colors.border}`,
        borderRadius: radius.sm,
        fontSize: fontSize.sm,
        fontWeight: active ? fontWeight.semibold : fontWeight.medium,
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.5 : 1,
      }}
    >
      {label}
    </button>
  );
}

/**
 * Heurística para detectar si una tx parece operación financiada por
 * descripción — útil en el detalle de tx para decidir si mostrar el
 * bloque, y en la lista del wizard de import para flagear filas.
 */
export function looksLikeFinancedOperation(description: string | null): boolean {
  if (!description) return false;
  const lower = description.toLowerCase();
  return (
    lower.includes('operacion financiada') ||
    lower.includes('operación financiada') ||
    lower.includes('operacion fraccionada') ||
    lower.includes('operación fraccionada') ||
    lower.includes('tarjeta financiada') ||
    lower.includes('compra a plazos')
  );
}
