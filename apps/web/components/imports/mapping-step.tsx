'use client';

import { useState, type FormEvent } from 'react';

import type { ImportColumnMappings } from '@finanzas/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@finanzas/ui';

import { Button } from '../ui/button';
import { TextInput } from '../ui/field';

const FIELD_DEFS = [
  {
    key: 'amount',
    label: 'Importe (obligatorio)',
    required: true,
    fallback: 'Importe',
    synonyms: ['amount', 'importe', 'monto', 'cantidad', 'cuantía', 'cuantia', 'valor'],
  },
  {
    key: 'occurred_at',
    label: 'Fecha (obligatorio)',
    required: true,
    fallback: 'Fecha',
    synonyms: [
      'date',
      'fecha',
      'fecha valor',
      'fecha operación',
      'fecha operacion',
      'fecha de operación',
      'fecha de operacion',
      'when',
    ],
  },
  {
    key: 'description',
    label: 'Descripción (opcional)',
    required: false,
    fallback: 'Concepto',
    synonyms: [
      'description',
      'descripción',
      'descripcion',
      'concepto',
      'detalle',
      'movimiento',
      'observaciones',
    ],
  },
  {
    key: 'category_name',
    label: 'Categoría (opcional)',
    required: false,
    fallback: 'Categoría',
    synonyms: ['category', 'categoría', 'categoria', 'tipo', 'clase'],
  },
] as const;

type FieldKey = (typeof FIELD_DEFS)[number]['key'];

function normalize(value: string): string {
  return value
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .trim();
}

function autoMapField(
  detectedHeaders: string[] | null,
  synonyms: readonly string[],
  fallback: string,
): string {
  if (detectedHeaders && detectedHeaders.length > 0) {
    const normalizedSynonyms = new Set(synonyms.map(normalize));
    const match = detectedHeaders.find((h) => normalizedSynonyms.has(normalize(h)));
    return match ?? '';
  }
  // XLSX / PDF: sin detección en cliente; sembramos un nombre canónico
  // típico de extractos bancarios en español. El usuario puede editarlo.
  return fallback;
}

function buildInitialValues(
  detectedHeaders: string[] | null,
): Record<FieldKey, string> {
  return FIELD_DEFS.reduce(
    (acc, def) => {
      acc[def.key] = autoMapField(detectedHeaders, def.synonyms, def.fallback);
      return acc;
    },
    {} as Record<FieldKey, string>,
  );
}

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
  const [values, setValues] = useState<Record<FieldKey, string>>(() =>
    buildInitialValues(detectedHeaders),
  );
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
        {detectedHeaders
          ? 'Hemos pre-rellenado los campos a partir de las cabeceras del CSV. Revísalos y edítalos si no coinciden. El importe debe ser positivo (el signo se infiere de la categoría).'
          : 'Hemos pre-rellenado los campos con los nombres típicos de un extracto en español. Edítalos para que coincidan con las columnas reales de tu fichero. El importe debe ser positivo (el signo se infiere de la categoría).'}
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
          {submitting ? 'Generando vista previa…' : 'Continuar →'}
        </Button>
      </div>
    </form>
  );
}
