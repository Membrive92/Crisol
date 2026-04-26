'use client';

import { useState, type FormEvent } from 'react';

import type { ImportColumnMappings } from '@finanzas/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@finanzas/ui';

import { Button } from '../ui/button';
import { TextInput } from '../ui/field';

const FIELD_DEFS = [
  { key: 'amount', label: 'Importe (obligatorio)', required: true },
  { key: 'occurred_at', label: 'Fecha (obligatorio)', required: true },
  { key: 'description', label: 'Descripción (opcional)', required: false },
  { key: 'category_name', label: 'Categoría (opcional)', required: false },
] as const;

type FieldKey = (typeof FIELD_DEFS)[number]['key'];

export interface MappingStepProps {
  detectedHeaders: string[] | null;
  submitting: boolean;
  errorMessage: string | null;
  onBack: () => void;
  onSubmit: (mappings: ImportColumnMappings) => void;
}

export function MappingStep({
  detectedHeaders,
  submitting,
  errorMessage,
  onBack,
  onSubmit,
}: MappingStepProps) {
  const [values, setValues] = useState<Record<FieldKey, string>>({
    amount: '',
    occurred_at: '',
    description: '',
    category_name: '',
  });
  const [activeField, setActiveField] = useState<FieldKey | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);

  function handleChange(field: FieldKey, value: string) {
    setValues((prev) => ({ ...prev, [field]: value }));
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setValidationError(null);

    const amount = values.amount.trim();
    const occurredAt = values.occurred_at.trim();
    if (!amount || !occurredAt) {
      setValidationError('Importe y Fecha son obligatorios');
      return;
    }

    const mappings: ImportColumnMappings = {
      amount,
      occurred_at: occurredAt,
      description: values.description.trim() || null,
      category_name: values.category_name.trim() || null,
    };

    onSubmit(mappings);
  }

  return (
    <form onSubmit={handleSubmit} noValidate>
      <p
        style={{
          marginTop: 0,
          marginBottom: spacing.md,
          fontSize: fontSize.sm,
          color: colors.textMuted,
        }}
      >
        Indica el nombre exacto de la columna del fichero para cada campo. El
        importe debe ser positivo (el signo se infiere de la categoría).
      </p>

      {detectedHeaders ? (
        <div
          style={{
            marginBottom: spacing.md,
            padding: spacing.sm,
            backgroundColor: colors.surfaceMuted,
            borderRadius: radius.sm,
          }}
        >
          <div
            style={{
              fontSize: fontSize.xs,
              fontWeight: fontWeight.semibold,
              color: colors.textMuted,
              marginBottom: spacing.xs,
              textTransform: 'uppercase',
              letterSpacing: 0.5,
            }}
          >
            Columnas detectadas {activeField ? `(click para asignar a "${activeField}")` : ''}
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: spacing.xs }}>
            {detectedHeaders.map((header) => (
              <button
                key={header}
                type="button"
                onClick={() => {
                  if (activeField) handleChange(activeField, header);
                }}
                disabled={!activeField}
                style={{
                  padding: `${spacing.xs}px ${spacing.sm}px`,
                  backgroundColor: colors.surface,
                  border: `1px solid ${colors.border}`,
                  borderRadius: radius.sm,
                  fontSize: fontSize.xs,
                  color: colors.text,
                  cursor: activeField ? 'pointer' : 'not-allowed',
                  opacity: activeField ? 1 : 0.6,
                }}
              >
                {header}
              </button>
            ))}
          </div>
        </div>
      ) : null}

      {FIELD_DEFS.map((field) => (
        <TextInput
          key={field.key}
          label={field.label}
          type="text"
          value={values[field.key]}
          onFocus={() => setActiveField(field.key)}
          onChange={(e) => handleChange(field.key, e.target.value)}
          placeholder="Nombre de la columna"
        />
      ))}

      {validationError ? (
        <div
          style={{
            color: colors.danger,
            fontSize: fontSize.sm,
            marginBottom: spacing.sm,
          }}
        >
          {validationError}
        </div>
      ) : null}

      {errorMessage ? (
        <div
          style={{
            color: colors.danger,
            fontSize: fontSize.sm,
            marginBottom: spacing.sm,
          }}
        >
          {errorMessage}
        </div>
      ) : null}

      <div style={{ display: 'flex', gap: spacing.sm, marginTop: spacing.md }}>
        <Button type="button" variant="ghost" onClick={onBack} disabled={submitting}>
          ← Atrás
        </Button>
        <Button type="submit" disabled={submitting}>
          {submitting ? 'Importando…' : 'Importar'}
        </Button>
      </div>
    </form>
  );
}
