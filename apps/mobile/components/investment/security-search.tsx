import { useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import { SEARCH_MIN_LENGTH, useAdoptSecurity, useSecuritySearch } from '@crisol/services';
import type { SecuritySearchHit, TickerRequiredDetail } from '@crisol/types';
import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';

/**
 * Buscador de valores en móvil — paridad con web (PHASE-44.8 E2).
 *
 * Lo que había antes era un `TextInput` de ticker que llamaba a `/resolve` con
 * lo tecleado: sin sugerencias, sin nombres y sin plaza, así que MCD entraba en
 * el catálogo como `UNKNOWN` mientras la web lo guardaba en `NYSE`. Ahora las
 * dos pantallas consultan las mismas dos capas locales —catálogo e índice de la
 * SEC— y adoptan por `listing_key`, que es lo que impide que el cliente decida
 * el mercado.
 *
 * Se conserva la escotilla de EDGAR para lo que el índice no cubre.
 */
/** Boundary de API: el único sitio que mira dentro de la respuesta HTTP cruda
 *  para distinguir la degradación diseñada (`ticker_required`) de un error. */
function extractAdoptError(error: unknown): TickerRequiredDetail | string | null {
  if (typeof error !== 'object' || error === null) return null;
  const response = (error as { response?: { data?: { detail?: unknown } } }).response;
  const detail = response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (
    typeof detail === 'object' &&
    detail !== null &&
    (detail as { code?: unknown }).code === 'ticker_required'
  ) {
    return detail as TickerRequiredDetail;
  }
  return null;
}

export function SecuritySearch({
  onSelect,
  placeholder = 'Ticker o nombre (ej. MCD)',
}: {
  /** `label` es lo que el usuario acaba de elegir, para que quien reciba el id
   *  pueda enseñarlo: un «Valor elegido ✓» mudo obliga a fiarse de memoria. */
  onSelect: (securityId: string, label?: string) => void;
  placeholder?: string;
}) {
  const [q, setQ] = useState('');
  const search = useSecuritySearch(q);
  const adopt = useAdoptSecurity();
  const query = q.trim();
  const results = search.data?.results ?? [];
  const notice = search.data?.notice ?? null;
  const indexReady = search.data?.index_ready ?? true;
  const directorySeededAt = search.data?.directory_seeded_at ?? null;
  const [tickerPrompt, setTickerPrompt] = useState<{
    listingKey: string;
    detail: TickerRequiredDetail;
  } | null>(null);
  const [manualTicker, setManualTicker] = useState('');
  const [serverMessage, setServerMessage] = useState<string | null>(null);

  async function adoptKey(listingKey: string, ticker?: string, label?: string): Promise<void> {
    setServerMessage(null);
    try {
      const body = ticker ? { listing_key: listingKey, ticker } : { listing_key: listingKey };
      const security = await adopt.mutateAsync(body);
      setTickerPrompt(null);
      setManualTicker('');
      onSelect(security.id, label ?? `${security.ticker} · ${security.name}`);
      setQ('');
    } catch (error) {
      const extracted = extractAdoptError(error);
      if (typeof extracted === 'string') setServerMessage(extracted);
      else if (extracted !== null) setTickerPrompt({ listingKey, detail: extracted });
    }
  }

  async function pick(hit: SecuritySearchHit): Promise<void> {
    const label = hit.ticker ? `${hit.ticker} · ${hit.name}` : hit.name;
    if (hit.id) {
      onSelect(hit.id, label);
      setQ('');
      return;
    }
    await adoptKey(hit.listing_key, undefined, label);
  }

  async function bringTyped(): Promise<void> {
    if (!query) return;
    await adoptKey(`typed:${query.toUpperCase()}`);
  }

  /**
   * Cambiar la búsqueda descarta el formulario de ticker manual y el mensaje
   * del servidor: si no, quedan pegados a la consulta anterior y pulsar
   * «Añadir» daría de alta el listing que ya no estás mirando.
   */
  function changeQuery(next: string): void {
    setQ(next);
    setTickerPrompt(null);
    setManualTicker('');
    setServerMessage(null);
  }

  return (
    <View style={{ gap: spacing.sm }}>
      <TextInput
        value={q}
        onChangeText={changeQuery}
        placeholder={placeholder}
        placeholderTextColor={colors.textSubtle}
        autoCapitalize="none"
        autoCorrect={false}
        style={styles.input}
      />

      {serverMessage ? (
        <Text style={styles.error}>{serverMessage}</Text>
      ) : adopt.isError && !tickerPrompt ? (
        <Text style={styles.error}>No se pudo añadir el valor. Comprueba el ticker.</Text>
      ) : null}

      {tickerPrompt ? (
        // Degradación diseñada del alta ext: (PHASE-44.14): el proveedor de
        // precios no reconoce el ISIN; la identidad viene pre-rellenada.
        <View style={styles.promptCard}>
          <Text style={styles.rowTitle} numberOfLines={2}>
            {tickerPrompt.detail.prefill.name} · {tickerPrompt.detail.prefill.mic} ·{' '}
            {tickerPrompt.detail.prefill.currency}
          </Text>
          <Text style={styles.hint}>{tickerPrompt.detail.message}</Text>
          <View style={{ flexDirection: 'row', gap: spacing.sm }}>
            <TextInput
              value={manualTicker}
              onChangeText={setManualTicker}
              placeholder="Símbolo local (ej. ITX)"
              placeholderTextColor={colors.textSubtle}
              autoCapitalize="characters"
              autoCorrect={false}
              style={[styles.input, { flex: 1 }]}
            />
            <Pressable
              onPress={() => {
                if (manualTicker.trim()) {
                  void adoptKey(tickerPrompt.listingKey, manualTicker.trim().toUpperCase());
                }
              }}
              disabled={adopt.isPending || !manualTicker.trim()}
              style={styles.promptBtn}
            >
              <Text style={styles.promptBtnText}>{adopt.isPending ? '…' : 'Añadir'}</Text>
            </Pressable>
          </View>
        </View>
      ) : null}

      {/* Callarse por debajo del mínimo se lee como «está roto» (fue un fallo
          real en la web, documentado en su test). */}
      {query.length > 0 && query.length < SEARCH_MIN_LENGTH ? (
        <Text style={styles.hint}>Escribe al menos {SEARCH_MIN_LENGTH} caracteres.</Text>
      ) : null}

      {query.length >= SEARCH_MIN_LENGTH ? (
        <View style={styles.list}>
          {results.map((hit) => (
            <Pressable
              key={hit.listing_key}
              onPress={() => void pick(hit)}
              disabled={adopt.isPending}
              style={styles.row}
            >
              <View style={{ flex: 1 }}>
                <Text style={styles.rowTitle} numberOfLines={1}>
                  {hit.ticker ? `${hit.ticker} · ` : ''}
                  {hit.name}
                </Text>
                {hit.exchange_label ? (
                  <Text style={styles.rowSub}>
                    {hit.exchange_label}
                    {!hit.ticker && hit.currency ? ` · ${hit.currency}` : ''}
                    {!hit.ticker && hit.isin ? ` · ${hit.isin}` : ''}
                  </Text>
                ) : null}
              </View>
              {!hit.analysis_available ? (
                <Text style={styles.badge}>sólo cartera</Text>
              ) : !hit.in_catalog ? (
                <Text style={styles.badge}>añadir</Text>
              ) : null}
            </Pressable>
          ))}

          {results.length === 0 && search.isFetching ? (
            <Text style={styles.placeholderRow}>Buscando…</Text>
          ) : null}

          {results.length === 0 && !search.isFetching && notice ? (
            // Un desplegable vacío se lee como «esa empresa no existe», que es
            // falso: lo que pasa es que no es un emisor de la SEC.
            <Text style={styles.placeholderRow}>{notice}</Text>
          ) : null}

          {results.length === 0 && !search.isFetching && directorySeededAt === null ? (
            <Text style={styles.placeholderRow}>
              El directorio de valores europeos no está sembrado, así que sólo se ha buscado
              en la SEC y en tu catálogo.
            </Text>
          ) : null}

          {results.length === 0 && !search.isFetching && !indexReady ? (
            <Text style={styles.placeholderRow}>
              El listado de emisores de la SEC no está disponible ahora mismo, así que sólo se ha
              buscado en tu catálogo.
            </Text>
          ) : null}

          {results.length === 0 && !search.isFetching ? (
            <Pressable onPress={() => void bringTyped()} disabled={adopt.isPending} style={styles.row}>
              <Text style={styles.escape}>
                {adopt.isPending
                  ? 'Buscando en EDGAR…'
                  : `Traer «${query.toUpperCase()}» de EDGAR`}
              </Text>
            </Pressable>
          ) : null}
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.surface,
    color: colors.text,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    fontSize: fontSize.md,
  },
  list: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.surface,
    overflow: 'hidden',
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  rowTitle: { color: colors.text, fontSize: fontSize.sm },
  rowSub: { color: colors.textSubtle, fontSize: fontSize.xs },
  badge: { color: colors.textSubtle, fontSize: fontSize.xs },
  placeholderRow: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    color: colors.textSubtle,
    fontSize: fontSize.xs,
    lineHeight: 18,
  },
  escape: { color: colors.primary, fontSize: fontSize.sm, fontWeight: fontWeight.semibold },
  promptCard: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.surface,
    padding: spacing.md,
    gap: spacing.sm,
  },
  promptBtn: {
    backgroundColor: colors.primary,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    justifyContent: 'center',
  },
  promptBtnText: { color: colors.onPrimary, fontSize: fontSize.sm, fontWeight: fontWeight.semibold },
  error: { color: colors.danger, fontSize: fontSize.sm },
  hint: { color: colors.textSubtle, fontSize: fontSize.xs },
});
