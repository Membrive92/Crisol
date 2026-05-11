import { useState } from 'react';
import {
  Image,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { useRouter } from 'expo-router';
import * as ImagePicker from 'expo-image-picker';

import {
  useConfirmReceipt,
  useExtractReceipt,
  useRejectReceipt,
} from '@crisol/services';
import { toast } from '@crisol/store';
import type { Receipt, ReceiptConfirmRequest, ReceiptExtraction } from '@crisol/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';

import { ReceiptCaptureForm } from '@/components/receipt-capture-form';
import { ConfirmDialog } from '@/components/ui/confirm-dialog';

interface PickedImage {
  uri: string;
  fileName: string;
  mimeType: string;
}

const DEFAULT_MIME = 'image/jpeg';

function inferMime(asset: ImagePicker.ImagePickerAsset): string {
  if (asset.mimeType) return asset.mimeType;
  const ext = asset.uri.split('.').pop()?.toLowerCase();
  if (ext === 'png') return 'image/png';
  if (ext === 'webp') return 'image/webp';
  if (ext === 'heic') return 'image/heic';
  if (ext === 'heif') return 'image/heif';
  return DEFAULT_MIME;
}

function inferFileName(asset: ImagePicker.ImagePickerAsset, mime: string): string {
  if (asset.fileName) return asset.fileName;
  const ext = mime.split('/')[1] ?? 'jpg';
  return `ticket.${ext}`;
}

async function buildFileFromAsset(picked: PickedImage): Promise<File> {
  // En React Native fetch da un Blob; lo envolvemos en un File para que
  // axios + FormData mande el filename y content-type correctos.
  const response = await fetch(picked.uri);
  const blob = await response.blob();
  return new File([blob], picked.fileName, { type: picked.mimeType });
}

export default function NewReceiptScreen() {
  const router = useRouter();
  const [picked, setPicked] = useState<PickedImage | null>(null);
  const [stagedReceipt, setStagedReceipt] = useState<Receipt | null>(null);
  const [stagedExtraction, setStagedExtraction] = useState<ReceiptExtraction | null>(null);
  const [confirmingReject, setConfirmingReject] = useState(false);

  const extractMutation = useExtractReceipt();
  const confirmMutation = useConfirmReceipt(stagedReceipt?.id ?? '');
  const rejectMutation = useRejectReceipt(stagedReceipt?.id ?? '');

  async function handlePickFromLibrary() {
    const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!perm.granted) {
      // PHASE-11.4: errores no bloqueantes pasan por toast; Alert
      // se reserva para confirms destructivos (handleReject).
      toast.warning('Concede acceso a la galería para subir tickets.');
      return;
    }
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      quality: 0.8,
    });
    if (result.canceled || result.assets.length === 0) return;
    const asset = result.assets[0]!;
    const mime = inferMime(asset);
    setPicked({ uri: asset.uri, fileName: inferFileName(asset, mime), mimeType: mime });
  }

  async function handleTakePhoto() {
    const perm = await ImagePicker.requestCameraPermissionsAsync();
    if (!perm.granted) {
      toast.warning('Concede acceso a la cámara para capturar tickets.');
      return;
    }
    const result = await ImagePicker.launchCameraAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      quality: 0.8,
    });
    if (result.canceled || result.assets.length === 0) return;
    const asset = result.assets[0]!;
    const mime = inferMime(asset);
    setPicked({ uri: asset.uri, fileName: inferFileName(asset, mime), mimeType: mime });
  }

  async function handleAnalyze() {
    if (!picked) return;
    try {
      const file = await buildFileFromAsset(picked);
      // Toast persistente con spinner mientras la IA local procesa el ticket.
      const loadingId = toast.loading('IA leyendo el ticket…');
      extractMutation.mutate(file, {
        onSuccess: (data) => {
          toast.dismiss(loadingId);
          setStagedReceipt(data.receipt);
          setStagedExtraction(data.extraction);
        },
        onError: (err) => {
          toast.dismiss(loadingId);
          toast.error(
            err instanceof Error
              ? `Error al analizar: ${err.message}`
              : 'No se pudo analizar el ticket. ¿Está Ollama corriendo?',
          );
        },
      });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'No se pudo leer la imagen');
    }
  }

  function handleConfirm(payload: ReceiptConfirmRequest) {
    if (!stagedReceipt) return;
    confirmMutation.mutate(payload, {
      onSuccess: () => {
        toast.success('Ticket añadido como transacción.');
        router.replace('/(modules)/personal-finance/(tabs)/receipts');
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
        router.replace('/(modules)/personal-finance/(tabs)/receipts');
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
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.title}>Nuevo ticket</Text>

      {!inExtraction ? (
        <View style={styles.card}>
          <Text style={styles.helper}>
            Toma una foto del ticket o súbela desde la galería. La IA local lee
            importe, fecha y comercio; tú confirmas o editas antes de crear la
            transacción.
          </Text>

          <View style={styles.buttonRow}>
            <TouchableOpacity style={styles.primaryButton} onPress={handleTakePhoto}>
              <Text style={styles.primaryButtonText}>Cámara</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.secondaryButton} onPress={handlePickFromLibrary}>
              <Text style={styles.secondaryButtonText}>Galería</Text>
            </TouchableOpacity>
          </View>

          {picked ? (
            <Image source={{ uri: picked.uri }} style={styles.preview} />
          ) : null}

          <TouchableOpacity
            style={[
              styles.primaryButton,
              styles.fullWidth,
              (!picked || extractMutation.isPending) && styles.disabled,
            ]}
            onPress={handleAnalyze}
            disabled={!picked || extractMutation.isPending}
          >
            <Text style={styles.primaryButtonText}>
              {extractMutation.isPending ? 'Analizando…' : 'Analizar'}
            </Text>
          </TouchableOpacity>
        </View>
      ) : (
        <View style={styles.card}>
          {/* `errorMessage` se gestiona via toast (PHASE-11.4); el prop
              opcional del form sigue disponible para errores locales
              de validación si en el futuro hace falta. */}
          <ReceiptCaptureForm
            extraction={stagedExtraction}
            submitting={confirmMutation.isPending || rejectMutation.isPending}
            onSubmit={handleConfirm}
            onReject={handleReject}
          />
        </View>
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
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.lg },
  title: {
    fontSize: fontSize.xl,
    fontWeight: fontWeight.semibold as '600',
    color: colors.text,
    marginBottom: spacing.lg,
  },
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  helper: {
    fontSize: fontSize.sm,
    color: colors.textMuted,
    marginBottom: spacing.md,
  },
  buttonRow: {
    flexDirection: 'row',
    gap: spacing.sm,
    marginBottom: spacing.md,
  },
  primaryButton: {
    backgroundColor: colors.primary,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.md,
    alignItems: 'center',
    flex: 1,
  },
  primaryButtonText: {
    color: colors.surface,
    fontSize: fontSize.sm,
    fontWeight: fontWeight.semibold as '600',
  },
  secondaryButton: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.primary,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.md,
    alignItems: 'center',
    flex: 1,
  },
  secondaryButtonText: {
    color: colors.primary,
    fontSize: fontSize.sm,
    fontWeight: fontWeight.semibold as '600',
  },
  fullWidth: { width: '100%' },
  disabled: { opacity: 0.5 },
  preview: {
    width: '100%',
    height: 240,
    resizeMode: 'contain',
    borderRadius: radius.sm,
    marginBottom: spacing.md,
    backgroundColor: colors.surfaceMuted,
  },
});
