'use client';

import { useState, type ChangeEvent, type FormEvent } from 'react';

import { useCategories } from '@finanzas/services';
import { colors, fontSize, fontWeight, spacing } from '@finanzas/ui';

import { Button } from '../ui/button';
import { Select, TextInput } from '../ui/field';

import { detectCsvHeaders } from './detect-csv-headers';

const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
const ACCEPTED_EXTENSIONS = ['.csv', '.tsv', '.xlsx', '.pdf'] as const;

export interface UploadStepValue {
  file: File;
  currency: string;
  defaultCategoryId: string | null;
  detectedHeaders: string[] | null;
}

export interface UploadStepProps {
  onContinue: (value: UploadStepValue) => void;
}

export function UploadStep({ onContinue }: UploadStepProps) {
  const { data: categories, isLoading: loadingCategories } = useCategories();
  const [file, setFile] = useState<File | null>(null);
  const [currency, setCurrency] = useState('EUR');
  const [defaultCategoryId, setDefaultCategoryId] = useState('');
  const [error, setError] = useState<string | null>(null);

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

    const trimmedCurrency = currency.trim().toUpperCase();
    if (trimmedCurrency.length !== 3) {
      setError('La moneda debe ser un código ISO de 3 letras (ej: EUR)');
      return;
    }

    const detectedHeaders = await detectCsvHeaders(file);

    onContinue({
      file,
      currency: trimmedCurrency,
      defaultCategoryId: defaultCategoryId || null,
      detectedHeaders,
    });
  }

  return (
    <form onSubmit={handleSubmit} noValidate>
      <label style={{ display: 'block', marginBottom: spacing.md }}>
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
        <input
          type="file"
          accept={ACCEPTED_EXTENSIONS.join(',')}
          onChange={handleFileChange}
          style={{ fontSize: fontSize.sm, color: colors.text }}
        />
        {file ? (
          <div
            style={{
              marginTop: spacing.xs,
              fontSize: fontSize.xs,
              color: colors.textMuted,
            }}
          >
            {file.name} · {(file.size / 1024).toFixed(1)} KB
          </div>
        ) : null}
      </label>

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
