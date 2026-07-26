import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';

import {
  useIngest,
  useResolveSecurity,
  useRunAnalysis,
  useStatements,
} from '@crisol/services';
import type { AnalysisRun, MetricBand } from '@crisol/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';

function bandColor(band: MetricBand): string {
  if (band === 'healthy') return colors.success;
  if (band === 'caution') return colors.warning;
  return colors.danger;
}

export default function AnalysisScreen() {
  const [ticker, setTicker] = useState('');
  const [securityId, setSecurityId] = useState<string | null>(null);
  const resolve = useResolveSecurity();
  const statements = useStatements(securityId, 'latest');
  const ingest = useIngest();
  const run = useRunAnalysis();
  const hasStatements = (statements.data?.length ?? 0) > 0;

  async function analyze(): Promise<void> {
    const value = ticker.trim().toUpperCase();
    if (!value) return;
    // Sin `exchange`: la plaza la decide el servidor (PHASE-44.8 E1). Mandar
    // `'US'` desde aquí creaba una fila paralela a la de la web para el mismo
    // valor, porque la clave única del catálogo es `(ticker, exchange)`.
    const security = await resolve.mutateAsync({ ticker: value });
    setSecurityId(security.id);
  }

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <View style={styles.searchRow}>
        <TextInput
          value={ticker}
          onChangeText={setTicker}
          placeholder="Ticker (ej. MCD)"
          placeholderTextColor={colors.textSubtle}
          autoCapitalize="characters"
          style={styles.input}
        />
        <Pressable onPress={() => void analyze()} disabled={resolve.isPending} style={styles.primaryBtn}>
          <Text style={styles.primaryBtnText}>{resolve.isPending ? '…' : 'Buscar'}</Text>
        </Pressable>
      </View>

      {securityId && !hasStatements ? (
        <Pressable
          onPress={() => void ingest.mutateAsync({ securityId, filings_back: 5 })}
          disabled={ingest.isPending}
          style={styles.primaryBtn}
        >
          <Text style={styles.primaryBtnText}>
            {ingest.isPending ? 'Descargando 10-K…' : 'Descargar 10-K (EDGAR)'}
          </Text>
        </Pressable>
      ) : null}

      {ingest.data?.status === 'failed' ? (
        <Text style={styles.error}>{ingest.data.error}</Text>
      ) : null}

      {hasStatements && !run.data ? (
        <Pressable
          onPress={() => void run.mutateAsync({ securityId: securityId as string })}
          disabled={run.isPending}
          style={styles.primaryBtn}
        >
          <Text style={styles.primaryBtnText}>
            {run.isPending ? 'Analizando…' : 'Ejecutar análisis'}
          </Text>
        </Pressable>
      ) : null}

      {run.data ? <Verdict run={run.data} /> : null}
    </ScrollView>
  );
}

function Verdict({ run }: { run: AnalysisRun }) {
  const { verdict, data_completeness: dc } = run;
  return (
    <View style={{ gap: spacing.sm }}>
      <Text style={styles.confidence}>
        Confianza {Math.round(Number(dc.value) * 100)}% · {verdict.safety_profile.label}
      </Text>
      {verdict.questions.map((q) => (
        <View key={q.key} style={[styles.card, { borderLeftWidth: 3, borderLeftColor: bandColor(q.verdict) }]}>
          <Text style={styles.question}>{q.question}</Text>
          <Text style={[styles.band, { color: bandColor(q.verdict) }]}>
            {q.verdict === 'healthy' ? 'Sano' : q.verdict === 'caution' ? 'Vigilar' : 'Riesgo'}
          </Text>
          {[...q.red_signals, ...q.amber_signals].length > 0 ? (
            <Text style={styles.signals}>{[...q.red_signals, ...q.amber_signals].join(' · ')}</Text>
          ) : null}
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { padding: spacing.md, gap: spacing.md },
  searchRow: { flexDirection: 'row', gap: spacing.sm },
  input: {
    flex: 1,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.surface,
    color: colors.text,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    fontSize: fontSize.md,
  },
  primaryBtn: {
    backgroundColor: colors.primary,
    borderRadius: radius.md,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    alignItems: 'center',
    justifyContent: 'center',
  },
  primaryBtnText: { color: colors.onPrimary, fontSize: fontSize.sm, fontWeight: fontWeight.semibold },
  error: { color: colors.danger, fontSize: fontSize.sm },
  confidence: { color: colors.textMuted, fontSize: fontSize.sm, fontWeight: fontWeight.semibold },
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    gap: spacing.xs,
  },
  question: { color: colors.text, fontSize: fontSize.sm, fontWeight: fontWeight.semibold },
  band: { fontSize: fontSize.xs, fontWeight: fontWeight.bold },
  signals: { color: colors.textMuted, fontSize: fontSize.xs },
});
