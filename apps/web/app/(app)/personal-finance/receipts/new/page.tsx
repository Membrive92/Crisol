'use client';

import { useState, type ChangeEvent } from 'react';
import { useRouter } from 'next/navigation';

import {
  useConfirmReceipt,
  useExtractReceipt,
  useRejectReceipt,
} from '@finanzas/services';
import { toast } from '@finanzas/store';
import type { Receipt, ReceiptConfirmRequest, ReceiptExtraction } from '@finanzas/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@finanzas/ui';

import {
  ExtractionSummary,
  ReceiptConfirmForm,
} from '@/components/receipts/confirm-form';
import { Button } from '@/components/ui/button';
import { Spinner } from '@/components/ui/spinner';
import { Card } from '@/components/ui/card';
import { ConfirmDialog } from '@/components/ui/confirm-dialog';

const ACCEPTED_IMAGE_TYPES = [
  'image/jpeg',
  'image/jpg',
  'image/png',
  'image/webp',
  'image/heic',
  'image/heif',
];
const MAX_BYTES = 8 * 1024 * 1024;

export default function NewReceiptPage() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [stagedReceipt, setStagedReceipt] = useState<Receipt | null>(null);
  const [stagedExtraction, setStagedExtraction] = useState<ReceiptExtraction | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [confirmingReject, setConfirmingReject] = useState(false);

  const extractMutation = useExtractReceipt();
  const confirmMutation = useConfirmReceipt(stagedReceipt?.id ?? '');
  const rejectMutation = useRejectReceipt(stagedReceipt?.id ?? '');

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    setUploadError(null);
    const next = event.target.files?.[0] ?? null;
    if (!next) {
      setFile(null);
      setPreviewUrl(null);
      return;
    }

    if (!ACCEPTED_IMAGE_TYPES.includes(next.type)) {
      setUploadError(`Formato no soportado. Acepta JPEG, PNG, WebP, HEIC, HEIF.`);
      return;
    }
    if (next.size > MAX_BYTES) {
      setUploadError(`La imagen supera ${MAX_BYTES / 1024 / 1024} MB`);
      return;
    }
    setFile(next);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(URL.createObjectURL(next));
  }

  function handleExtract() {
    if (!file) return;
    setUploadError(null);
    // Toast persistente con spinner: la inferencia visión en CPU
    // puede tardar 60-120s. Sin feedback el usuario asume cuelgue.
    const loadingId = toast.loading('IA leyendo el ticket…');
    extractMutation.mutate(file, {
      onSuccess: (data) => {
        toast.dismiss(loadingId);
        setStagedReceipt(data.receipt);
        setStagedExtraction(data.extraction);
      },
      onError: (err) => {
        toast.dismiss(loadingId);
        // PHASE-11.5: error de extracción al toast — antes era un
        // <div> rojo inline que el usuario podía perder al hacer
        // scroll. La causa #1 en dev es Ollama no corriendo, lo
        // sugerimos cuando el mensaje no aporta detalle.
        toast.error(
          err instanceof Error
            ? `Error al analizar: ${err.message}`
            : 'No se pudo analizar el ticket. ¿Está Ollama corriendo?',
        );
      },
    });
  }

  function handleConfirm(payload: ReceiptConfirmRequest) {
    if (!stagedReceipt) return;
    confirmMutation.mutate(payload, {
      onSuccess: () => {
        toast.success('Ticket añadido como transacción.');
        router.push('/personal-finance/receipts');
      },
      onError: (err) => {
        toast.error(
          err instanceof Error
            ? `Error al confirmar: ${err.message}`
            : 'Error al confirmar el ticket.',
        );
      },
    });
  }

  function handleReject() {
    if (!stagedReceipt) return;
    setConfirmingReject(true);
  }

  function confirmReject() {
    if (!stagedReceipt) return;
    setConfirmingReject(false);
    rejectMutation.mutate(undefined, {
      onSuccess: () => {
        toast.info('Ticket rechazado.');
        router.push('/personal-finance/receipts');
      },
      onError: (err) => {
        toast.error(
          err instanceof Error
            ? `Error al rechazar: ${err.message}`
            : 'Error al rechazar el ticket.',
        );
      },
    });
  }

  const inExtraction = stagedReceipt !== null && stagedExtraction !== null;

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
        Subir ticket
      </h1>

      {!inExtraction ? (
        <Card style={{ padding: spacing.lg }}>
          <p
            style={{
              marginTop: 0,
              fontSize: fontSize.sm,
              color: colors.textMuted,
            }}
          >
            Sube una foto del ticket. La IA local lee importe, fecha, comercio
            y líneas; tú confirmas o editas antes de crear la transacción.
          </p>

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
              Imagen (JPEG / PNG / WebP / HEIC, máx 8 MB)
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
                {file ? file.name : 'Ningún archivo seleccionado'}
              </span>
              <input
                type="file"
                accept={ACCEPTED_IMAGE_TYPES.join(',')}
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

          {previewUrl ? (
            <img
              src={previewUrl}
              alt="Vista previa"
              style={{
                maxWidth: '100%',
                maxHeight: 320,
                marginBottom: spacing.md,
                borderRadius: 8,
                border: `1px solid ${colors.border}`,
              }}
            />
          ) : null}

          {/* `uploadError` (validación local: tipo / tamaño) se queda
              inline porque es contexto del input. Errores de
              extracción (red / Ollama) se muestran via toast. */}
          {uploadError ? (
            <div style={{ color: colors.danger, fontSize: fontSize.sm, marginBottom: spacing.sm }}>
              {uploadError}
            </div>
          ) : null}

          <div style={{ display: 'flex', gap: spacing.sm }}>
            <Button onClick={handleExtract} disabled={!file || extractMutation.isPending}>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                {extractMutation.isPending ? (
                  <Spinner size={14} color={colors.onPrimary} />
                ) : null}
                {extractMutation.isPending ? 'Analizando…' : 'Analizar ticket'}
              </span>
            </Button>
          </div>
        </Card>
      ) : (
        <Card style={{ padding: spacing.lg }}>
          {/* PHASE-11.5: confirm/reject errors van por toast; el prop
              `errorMessage` queda opcional en el form para futuras
              validaciones locales que tengan sentido inline. */}
          <ReceiptConfirmForm
            extraction={stagedExtraction}
            submitting={confirmMutation.isPending || rejectMutation.isPending}
            onSubmit={handleConfirm}
            onReject={handleReject}
          />
          <ExtractionSummary extraction={stagedExtraction} />
        </Card>
      )}

      <ConfirmDialog
        open={confirmingReject}
        title="¿Rechazar este ticket?"
        description="La transacción no se creará y el ticket quedará marcado como rechazado."
        confirmLabel="Rechazar"
        cancelLabel="Atrás"
        tone="danger"
        loading={rejectMutation.isPending}
        onConfirm={confirmReject}
        onCancel={() => setConfirmingReject(false)}
      />
    </div>
  );
}
