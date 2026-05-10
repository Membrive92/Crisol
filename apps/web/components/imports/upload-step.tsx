'use client';

import { useEffect, useState, type ChangeEvent, type FormEvent } from 'react';

import { useAccounts, useCategories } from '@finanzas/services';
import { colors, fontSize, fontWeight, radius, spacing } from '@finanzas/ui';

import { Button } from '../ui/button';
import { Select, TextInput } from '../ui/field';

import { detectCsvHeaders } from './detect-csv-headers';

const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
const ACCEPTED_EXTENSIONS = ['.csv', '.tsv', '.xlsx', '.pdf'] as const;

export interface UploadStepValue {
  file: File;
  /** PHASE-19.1: cuenta a la que se imputarán las txs del lote. */
  accountId: string;
  currency: string;
  defaultCategoryId: string | null;
  detectedHeaders: string[] | null;
}

export interface UploadStepProps {
  onContinue: (value: UploadStepValue) => void;
}

export function UploadStep({ onContinue }: UploadStepProps) {
  const { data: categories, isLoading: loadingCategories } = useCategories();
  const { data: accounts, isLoading: loadingAccounts } = useAccounts();
  const [file, setFile] = useState<File | null>(null);
  const [accountId, setAccountId] = useState('');
  const [currency, setCurrency] = useState('EUR');
  const [defaultCategoryId, setDefaultCategoryId] = useState('');
  const [error, setError] = useState<string | null>(null);

  // Pre-seleccionar la primera cuenta cuando se cargue la lista. La
  // moneda del form sigue siendo independiente — el usuario puede
  // tener una cuenta EUR y querer importar un extracto USD.
  useEffect(() => {
    if (!accounts || accounts.length === 0) return;
    if (!accountId) {
      const first = accounts[0];
      if (first) {
        setAccountId(first.id);
        // Si no han tocado la moneda, sincronizamos con la cuenta — es
        // el caso más común (extracto del banco en su moneda nativa).
        setCurrency((prev) => (prev === 'EUR' ? first.currency : prev));
      }
    }
  }, [accounts, accountId]);

  const accountList = accounts ?? [];

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    setError(null);
    const next = event.target.files?.[0] ?? null;

    if (next) {
      const lower = next.name.toLowerCase();
      const accepted = ACCEPTED_EXTENSIONS.some((ext) => lower.endsWith(ext));
      if (!accepted) {
        setError(`Formato no soportado. Acepta ${ACCEPTED_EXTENSIONS.join(', ')}`);
        setFile(null);
        return;
      }
      if (next.size > MAX_UPLOAD_BYTES) {
        setError(`El fichero supera el límite de ${MAX_UPLOAD_BYTES / 1024 / 1024} MB`);
        setFile(null);
        return;
      }
    }

    setFile(next);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (!file) {
      setError('Selecciona un fichero');
      return;
    }

    if (!accountId) {
      setError('Selecciona la cuenta a la que se imputarán las transacciones');
      return;
    }

    const trimmedCurrency = currency.trim().toUpperCase();
    if (trimmedCurrency.length !== 3) {
      setError('La moneda debe ser un código ISO de 3 letras (ej: EUR)');
      return;
    }

    const detectedHeaders = await detectCsvHeaders(file);

    onContinue({
      file,
      accountId,
      currency: trimmedCurrency,
      defaultCategoryId: defaultCategoryId || null,
      detectedHeaders,
    });
  }

  return (
    <form onSubmit={handleSubmit} noValidate>
      <Select
        label="Cuenta destino"
        value={accountId}
        onChange={(e) => setAccountId(e.target.value)}
        disabled={loadingAccounts || accountList.length === 0}
        required
      >
        {accountList.length === 0 ? (
          <option value="">— Sin cuentas disponibles —</option>
        ) : null}
        {accountList.map((a) => (
          <option key={a.id} value={a.id}>
            {a.icon ? `${a.icon} ` : ''}
            {a.name} ({a.currency})
          </option>
        ))}
      </Select>

      <div style={{ marginBottom: spacing.md }}>
        <span
          style={{
            display: 'block',
            marginBottom: spacing.xs,
            fontSize: fontSize.sm,
            fontWeight: fontWeight.medium,
            color: colors.text,
          }}
        >
          Fichero (CSV / XLSX / PDF, máx 10 MB)
        </span>
        <label
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: spacing.sm,
            cursor: 'pointer',
          }}
        >
          <span
            style={{
              padding: `${spacing.sm}px ${spacing.md}px`,
              borderRadius: radius.md,
              fontSize: fontSize.sm,
              fontWeight: fontWeight.semibold,
              backgroundColor: 'transparent',
              color: colors.text,
              border: `1px solid ${colors.border}`,
            }}
          >
            Seleccionar archivo
          </span>
          <span style={{ fontSize: fontSize.sm, color: colors.textMuted }}>
            {file
              ? `${file.name} · ${(file.size / 1024).toFixed(1)} KB`
              : 'Ningún archivo seleccionado'}
          </span>
          <input
            type="file"
            accept={ACCEPTED_EXTENSIONS.join(',')}
            onChange={handleFileChange}
            style={{
              position: 'absolute',
              width: 1,
              height: 1,
              padding: 0,
              margin: -1,
              overflow: 'hidden',
              clip: 'rect(0, 0, 0, 0)',
              whiteSpace: 'nowrap',
              border: 0,
            }}
          />
        </label>
      </div>

      <TextInput
        label="Moneda"
        type="text"
        maxLength={3}
        value={currency}
        onChange={(e) => setCurrency(e.target.value)}
      />

      <Select
        label="Categoría por defecto (opcional)"
        value={defaultCategoryId}
        onChange={(e) => setDefaultCategoryId(e.target.value)}
        disabled={loadingCategories}
      >
        <option value="">— Sin categoría por defecto —</option>
        {(categories ?? []).map((c) => (
          <option key={c.id} value={c.id}>
            {c.name} ({c.kind === 'income' ? 'Ingreso' : 'Gasto'})
          </option>
        ))}
      </Select>

      {error ? (
        <div
          style={{
            color: colors.danger,
            fontSize: fontSize.sm,
            marginBottom: spacing.sm,
          }}
        >
          {error}
        </div>
      ) : null}

      <div style={{ display: 'flex', gap: spacing.sm, marginTop: spacing.md }}>
        <Button type="submit">Continuar →</Button>
      </div>
    </form>
  );
}
