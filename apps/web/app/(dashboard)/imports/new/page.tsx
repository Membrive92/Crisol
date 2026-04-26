'use client';

import { useState } from 'react';

import { useCreateImport } from '@finanzas/services';
import type { ImportColumnMappings, ImportJob } from '@finanzas/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@finanzas/ui';

import { MappingStep } from '@/components/imports/mapping-step';
import { ResultStep } from '@/components/imports/result-step';
import { UploadStep, type UploadStepValue } from '@/components/imports/upload-step';
import { Card } from '@/components/ui/card';

type Step = 'upload' | 'mapping' | 'result';

const STEPS: { key: Step; label: string }[] = [
  { key: 'upload', label: '1. Fichero' },
  { key: 'mapping', label: '2. Mapeo' },
  { key: 'result', label: '3. Resultado' },
];

export default function NewImportPage() {
  const [step, setStep] = useState<Step>('upload');
  const [uploadValue, setUploadValue] = useState<UploadStepValue | null>(null);
  const [result, setResult] = useState<ImportJob | null>(null);
  const mutation = useCreateImport();

  function handleUploadContinue(value: UploadStepValue) {
    setUploadValue(value);
    setStep('mapping');
    mutation.reset();
  }

  function handleMappingBack() {
    setStep('upload');
    mutation.reset();
  }

  function handleMappingSubmit(mappings: ImportColumnMappings) {
    if (!uploadValue) return;
    mutation.mutate(
      {
        file: uploadValue.file,
        columnMappings: mappings,
        currency: uploadValue.currency,
        defaultCategoryId: uploadValue.defaultCategoryId,
      },
      {
        onSuccess: (job) => {
          setResult(job);
          setStep('result');
        },
      },
    );
  }

  function handleRestart() {
    setUploadValue(null);
    setResult(null);
    mutation.reset();
    setStep('upload');
  }

  return (
    <div style={{ maxWidth: 720, margin: '0 auto', padding: spacing.lg }}>
      <h1
        style={{
          fontSize: fontSize.xl,
          color: colors.text,
          marginTop: 0,
          marginBottom: spacing.lg,
        }}
      >
        Nueva importación
      </h1>

      <Stepper currentStep={step} />

      <Card style={{ padding: spacing.lg }}>
        {step === 'upload' ? <UploadStep onContinue={handleUploadContinue} /> : null}
        {step === 'mapping' && uploadValue ? (
          <MappingStep
            detectedHeaders={uploadValue.detectedHeaders}
            submitting={mutation.isPending}
            errorMessage={
              mutation.isError
                ? mutation.error instanceof Error
                  ? mutation.error.message
                  : 'Error al importar'
                : null
            }
            onBack={handleMappingBack}
            onSubmit={handleMappingSubmit}
          />
        ) : null}
        {step === 'result' && result ? (
          <ResultStep job={result} onRestart={handleRestart} />
        ) : null}
      </Card>
    </div>
  );
}

function Stepper({ currentStep }: { currentStep: Step }) {
  const currentIndex = STEPS.findIndex((s) => s.key === currentStep);
  return (
    <ol
      style={{
        listStyle: 'none',
        padding: 0,
        margin: `0 0 ${spacing.lg}px 0`,
        display: 'flex',
        gap: spacing.sm,
      }}
    >
      {STEPS.map((s, index) => {
        const isActive = index === currentIndex;
        const isDone = index < currentIndex;
        return (
          <li
            key={s.key}
            style={{
              flex: 1,
              padding: `${spacing.xs}px ${spacing.sm}px`,
              borderRadius: radius.sm,
              backgroundColor: isActive
                ? colors.primary
                : isDone
                  ? colors.surfaceMuted
                  : colors.surface,
              color: isActive ? colors.surface : isDone ? colors.text : colors.textMuted,
              border: `1px solid ${isActive ? colors.primary : colors.border}`,
              fontSize: fontSize.sm,
              fontWeight: fontWeight.medium,
              textAlign: 'center',
            }}
          >
            {s.label}
          </li>
        );
      })}
    </ol>
  );
}
