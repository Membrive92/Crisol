'use client';

import { useState } from 'react';

import {
  useAiSuggestImport,
  useCategories,
  useCommitImport,
  usePreviewImport,
} from '@crisol/services';
import { toast } from '@crisol/store';
import type {
  ImportColumnMappings,
  ImportJob,
  ImportPreviewResponse,
  ImportWarningKey,
} from '@crisol/types';
import {
  colors,
  fontSize,
  fontWeight,
  formatAmount,
  formatDate,
  layout,
  radius,
  spacing,
} from '@crisol/ui';

import { MappingStep } from '@/components/imports/mapping-step';
import { PreviewStep } from '@/components/imports/preview-step';
import { ResultStep } from '@/components/imports/result-step';
import { UploadStep, type UploadStepValue } from '@/components/imports/upload-step';
import { Card } from '@/components/ui/card';

type Step = 'upload' | 'mapping' | 'preview' | 'result';

const STEPS: { key: Step; label: string }[] = [
  { key: 'upload', label: '1. Fichero' },
  { key: 'mapping', label: '2. Mapeo' },
  { key: 'preview', label: '3. Vista previa' },
  { key: 'result', label: '4. Resultado' },
];

export default function NewImportPage() {
  const [step, setStep] = useState<Step>('upload');
  const [uploadValue, setUploadValue] = useState<UploadStepValue | null>(null);
  const [mappings, setMappings] = useState<ImportColumnMappings | null>(null);
  const [preview, setPreview] = useState<ImportPreviewResponse | null>(null);
  const [result, setResult] = useState<ImportJob | null>(null);

  const previewMutation = usePreviewImport();
  const commitMutation = useCommitImport();
  const aiSuggestMutation = useAiSuggestImport();
  const { data: categories } = useCategories();

  async function handleAiSuggest(): Promise<Record<string, string | null> | undefined> {
    if (!preview) return undefined;
    const loadingId = toast.loading('IA sugiriendo categorías…');
    try {
      const { suggestions } = await aiSuggestMutation.mutateAsync(preview.job_id);
      toast.dismiss(loadingId);
      const applied = Object.values(suggestions).filter(Boolean).length;
      if (applied === 0) {
        toast.info('La IA no encontró categoría clara para los conceptos pendientes.');
      } else {
        toast.success(
          `IA sugirió ${applied} ${applied === 1 ? 'categoría' : 'categorías'}.`,
        );
      }
      return suggestions;
    } catch (err) {
      toast.dismiss(loadingId);
      toast.error(
        err instanceof Error
          ? `Error con IA: ${err.message}`
          : 'Error al sugerir con IA',
      );
      return undefined;
    }
  }

  function handleUploadContinue(value: UploadStepValue) {
    setUploadValue(value);
    setStep('mapping');
    previewMutation.reset();
    commitMutation.reset();
  }

  function handleMappingBack() {
    setStep('upload');
    previewMutation.reset();
  }

  function handleMappingSubmit(nextMappings: ImportColumnMappings) {
    if (!uploadValue) return;
    setMappings(nextMappings);
    previewMutation.mutate(
      {
        accountId: uploadValue.accountId,
        file: uploadValue.file,
        columnMappings: nextMappings,
        currency: uploadValue.currency,
        defaultCategoryId: uploadValue.defaultCategoryId,
      },
      {
        onSuccess: (data) => {
          setPreview(data);
          setStep('preview');
        },
        onError: (err) => {
          toast.error(
            err instanceof Error
              ? `Error al previsualizar: ${err.message}`
              : 'Error al previsualizar',
          );
        },
      },
    );
  }

  function handlePreviewBack() {
    setStep('mapping');
    previewMutation.reset();
  }

  function handlePreviewRetryWithVision() {
    if (!uploadValue || !mappings) return;
    // Toast persistente con cronómetro mientras Ollama procesa las
    // páginas — la inferencia visión en CPU puede tardar varios
    // minutos y sin feedback el usuario asume que la app está colgada.
    const loadingId = toast.loading(
      'IA leyendo las páginas del PDF…',
    );
    previewMutation.mutate(
      {
        accountId: uploadValue.accountId,
        file: uploadValue.file,
        columnMappings: mappings,
        currency: uploadValue.currency,
        defaultCategoryId: uploadValue.defaultCategoryId,
        forceVision: true,
      },
      {
        onSuccess: (data) => {
          toast.dismiss(loadingId);
          setPreview(data);
          toast.info(`IA detectó ${data.total_rows} filas.`);
        },
        onError: (err) => {
          toast.dismiss(loadingId);
          toast.error(
            err instanceof Error
              ? `Error al procesar con IA: ${err.message}`
              : 'Error al procesar con IA',
          );
        },
      },
    );
  }

  function handlePreviewConfirm(
    categoryOverrides: Record<string, string>,
    acknowledgedWarnings: ImportWarningKey[],
  ) {
    if (!preview) return;
    commitMutation.mutate(
      {
        jobId: preview.job_id,
        ...(Object.keys(categoryOverrides).length > 0
          ? { categoryOverrides }
          : {}),
        // PHASE-47.A — sin los avisos reconocidos el backend responde 409.
        ...(acknowledgedWarnings.length > 0 ? { acknowledgedWarnings } : {}),
      },
      {
        onSuccess: (job) => {
          setResult(job);
          setStep('result');
          toast.success(`Importación completada: ${job.rows_ok} filas añadidas.`);
          // PHASE-39 — si el fichero traía columna Saldo, el backend ancla
          // el saldo real de la cuenta al del extracto.
          if (job.balance_anchor) {
            toast.info(
              `Saldo de la cuenta anclado a ${formatAmount(
                job.balance_anchor.balance,
                uploadValue?.currency ?? 'EUR',
              )} (${formatDate(job.balance_anchor.date)})`,
            );
          }
        },
        onError: (err) => {
          toast.error(
            err instanceof Error
              ? `Error al confirmar: ${err.message}`
              : 'Error al confirmar la importación',
          );
        },
      },
    );
  }

  function handleRestart() {
    setUploadValue(null);
    setMappings(null);
    setPreview(null);
    setResult(null);
    previewMutation.reset();
    commitMutation.reset();
    setStep('upload');
  }

  const canRetryWithVision =
    preview !== null &&
    (preview.source === 'pdfplumber_smart' ||
      preview.source === 'pdfplumber_legacy');

  return (
    <div style={{ maxWidth: layout.pageNarrow, margin: '0 auto', padding: spacing.lg }}>
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
            submitting={previewMutation.isPending}
            errorMessage={
              previewMutation.isError
                ? previewMutation.error instanceof Error
                  ? previewMutation.error.message
                  : 'Error al generar el preview'
                : null
            }
            onBack={handleMappingBack}
            onSubmit={handleMappingSubmit}
          />
        ) : null}
        {step === 'preview' && preview ? (
          <PreviewStep
            preview={preview}
            committing={commitMutation.isPending}
            reprocessing={previewMutation.isPending}
            canRetryWithVision={canRetryWithVision}
            categories={categories ?? []}
            errorMessage={
              commitMutation.isError
                ? commitMutation.error instanceof Error
                  ? commitMutation.error.message
                  : 'Error al confirmar'
                : null
            }
            onConfirm={handlePreviewConfirm}
            onRetryWithVision={handlePreviewRetryWithVision}
            onBack={handlePreviewBack}
            onAiSuggest={handleAiSuggest}
            aiSuggesting={aiSuggestMutation.isPending}
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
