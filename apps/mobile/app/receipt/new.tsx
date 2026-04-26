import { useState } from 'react';
import {
  Alert,
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
} from '@finanzas/services';
import type { Receipt, ReceiptConfirmRequest, ReceiptExtraction } from '@finanzas/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@finanzas/ui';

import { ReceiptCaptureForm } from '@/components/receipt-capture-form';

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

  const extractMutation = useExtractReceipt();
  const confirmMutation = useConfirmReceipt(stagedReceipt?.id ?? '');
  const rejectMutation = useRejectReceipt(stagedReceipt?.id ?? '');

  async function handlePickFromLibrary() {
    const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!perm.granted) {
      Alert.alert('Permiso necesario', 'Concede acceso a la galería para subir tickets.');
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
      Alert.alert('Permiso necesario', 'Concede acceso a la cámara para capturar tickets.');
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
      extractMutation.mutate(file, {
        onSuccess: (data) => {
          setStagedReceipt(data.receipt);
          setStagedExtraction(data.extraction);
        },
      });
    } catch (err) {
      Alert.alert('Error', err instanceof Error ? err.message : 'No se pudo leer la imagen');
    }
  }

  function handleConfirm(payload: ReceiptConfirmRequest) {
    if (!stagedReceipt) return;
    confirmMutation.mutate(payload, {
      onSuccess: () => router.replace('/(tabs)/receipts'),
    });
  }

  function handleReject() {
    if (!stagedReceipt) return;
    Alert.alert('Rechazar ticket', '¿Seguro? La transacción no se creará.', [
      { text: 'Cancelar', style: 'cancel' },
      {
        text: 'Rechazar',
        style: 'destructive',
        onPress: () =>
          rejectMutation.mutate(undefined, {
            onSuccess: () => router.replace('/(tabs)/receipts'),
          }),
      },
    ]);
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

          {extractMutation.isError ? (
            <Text style={styles.errorText}>
              {extractMutation.error instanceof Error
                ? extractMutation.error.message
                : 'Error al extraer'}
            </Text>
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
          <ReceiptCaptureForm
            extraction={stagedExtraction}
            submitting={confirmMutation.isPending || rejectMutation.isPending}
            errorMessage={
              confirmMutation.isError
                ? confirmMutation.error instanceof Error
                  ? confirmMutation.error.message
                  : 'Error al confirmar'
                : null
            }
            onSubmit={handleConfirm}
            onReject={handleReject}
          />
        </View>
      )}
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
  errorText: {
    color: colors.danger,
    fontSize: fontSize.sm,
    marginBottom: spacing.sm,
  },
});
