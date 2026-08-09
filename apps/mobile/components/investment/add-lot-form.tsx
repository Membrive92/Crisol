import { useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import { formatApiError, useCreateLot } from '@crisol/services';
import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';

import { SecuritySearch } from './security-search';

/**
 * Alta de una compra en móvil (PHASE-44.8 E4).
 *
 * La pantalla de Cartera era de **sólo lectura** desde PHASE-44.7 —decía
 * literalmente «Añádelas desde la web»—, así que lo que faltaba no era el
 * buscador sino el flujo entero. Con el buscador de E2/E5 ya en móvil, esto es
 * el formulario que lo consume.
 *
 * Mismos tres campos que la web y el mismo endpoint: cantidad, precio y fecha.
 * El `fx_rate_at_trade` NO se pide — lo deriva el servidor del tipo del BCE a la
 * fecha de la operación (PHASE-44.11), y pedirlo aquí invitaría a rellenarlo con
 * un `1` que sería un dato ficticio (la lección que costó el lote de JNJ).
 */
export function AddLotForm({ onDone }: { onDone: () => void }) {
  const [securityId, setSecurityId] = useState<string | null>(null);
  const [securityLabel, setSecurityLabel] = useState<string>('');
  const [quantity, setQuantity] = useState('');
  const [price, setPrice] = useState('');
  const [tradeDate, setTradeDate] = useState(todayIso());
  const createLot = useCreateLot();

  const dateValid = /^\d{4}-\d{2}-\d{2}$/.test(tradeDate);
  const ready = Boolean(securityId) && numeric(quantity) && numeric(price) && dateValid;

  async function submit(): Promise<void> {
    if (!securityId || !ready) return;
    await createLot.mutateAsync({
      security_id: securityId,
      trade_date: tradeDate,
      // Coma decimal → punto: en un teclado español la coma es lo natural, y
      // el backend espera `Decimal` serializado con punto.
      quantity: quantity.replace(',', '.'),
      price: price.replace(',', '.'),
    });
    setSecurityId(null);
    setSecurityLabel('');
    setQuantity('');
    setPrice('');
    onDone();
  }

  return (
    <View style={styles.wrap}>
      {securityId ? (
        <View style={styles.chosenRow}>
          <Text style={styles.chosen} numberOfLines={1}>
            {securityLabel || 'Valor elegido'}
          </Text>
          <Pressable
            onPress={() => {
              setSecurityId(null);
              setSecurityLabel('');
            }}
          >
            <Text style={styles.link}>cambiar</Text>
          </Pressable>
        </View>
      ) : (
        <SecuritySearch
          placeholder="Valor de la compra"
          onSelect={(id, label) => {
            setSecurityId(id);
            setSecurityLabel(label ?? '');
          }}
        />
      )}

      <View style={styles.row}>
        <TextInput
          value={quantity}
          onChangeText={setQuantity}
          placeholder="Cantidad"
          placeholderTextColor={colors.textSubtle}
          keyboardType="decimal-pad"
          style={[styles.input, { flex: 1 }]}
        />
        <TextInput
          value={price}
          onChangeText={setPrice}
          placeholder="Precio"
          placeholderTextColor={colors.textSubtle}
          keyboardType="decimal-pad"
          style={[styles.input, { flex: 1 }]}
        />
      </View>

      <TextInput
        value={tradeDate}
        onChangeText={setTradeDate}
        placeholder="AAAA-MM-DD"
        placeholderTextColor={colors.textSubtle}
        autoCapitalize="none"
        autoCorrect={false}
        style={styles.input}
      />
      {tradeDate && !dateValid ? (
        <Text style={styles.error}>La fecha va como AAAA-MM-DD (p. ej. 2026-08-07).</Text>
      ) : null}

      <Pressable
        onPress={() => void submit()}
        disabled={!ready || createLot.isPending}
        style={[styles.primaryBtn, (!ready || createLot.isPending) && styles.btnDisabled]}
      >
        <Text style={styles.primaryBtnText}>
          {createLot.isPending ? 'Añadiendo…' : 'Añadir compra'}
        </Text>
      </Pressable>

      {createLot.isError ? (
        <Text style={styles.error}>
          {formatApiError(createLot.error, 'No se pudo añadir la compra.')}
        </Text>
      ) : null}
    </View>
  );
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

/** Un número positivo con coma o punto. Vacío no cuenta. */
function numeric(value: string): boolean {
  const parsed = Number(value.replace(',', '.'));
  return value.trim() !== '' && Number.isFinite(parsed) && parsed > 0;
}

const styles = StyleSheet.create({
  wrap: { gap: spacing.sm },
  row: { flexDirection: 'row', gap: spacing.sm },
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
  chosenRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  chosen: { flex: 1, color: colors.text, fontSize: fontSize.sm, fontWeight: fontWeight.semibold },
  link: { color: colors.primary, fontSize: fontSize.sm },
  primaryBtn: {
    backgroundColor: colors.primary,
    borderRadius: radius.md,
    paddingVertical: spacing.sm,
    alignItems: 'center',
  },
  btnDisabled: { opacity: 0.6 },
  primaryBtnText: {
    color: colors.onPrimary,
    fontSize: fontSize.sm,
    fontWeight: fontWeight.semibold,
  },
  error: { color: colors.danger, fontSize: fontSize.sm },
});
