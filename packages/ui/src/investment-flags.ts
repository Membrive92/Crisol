import type { EngineFlag, FlagSeverity } from '@crisol/types';

/**
 * Agrupación de las banderas del motor — capa PURA compartida (PHASE-44.8).
 *
 * El motor emite las banderas **por ejercicio o por racha** y la síntesis las
 * concatena sin deduplicar: una empresa que diluye siete años seguidos produce
 * siete tarjetas idénticas. Agrupar es la diferencia entre un hallazgo y una
 * pared de repeticiones — y en una pantalla de móvil, entre leerlo y no leerlo.
 */

export const FLAG_SEVERITY_RANK: Record<FlagSeverity, number> = { red: 2, amber: 1, info: 0 };

export const FLAG_SEVERITY_LABEL: Record<FlagSeverity, string> = {
  red: 'Grave',
  amber: 'Atención',
  info: 'Informativa',
};

export interface GroupedFlag {
  key: string;
  severity: FlagSeverity;
  messages: string[];
  evidence: Record<string, unknown>[];
}

/** Agrupa por clave, quedándose con la peor severidad, y ordena de peor a mejor. */
export function groupFlags(flags: EngineFlag[]): GroupedFlag[] {
  const byKey = new Map<string, GroupedFlag>();
  for (const flag of flags) {
    const existing = byKey.get(flag.key);
    if (!existing) {
      byKey.set(flag.key, {
        key: flag.key,
        severity: flag.severity,
        messages: [flag.message],
        evidence: [flag.evidence],
      });
      continue;
    }
    if (FLAG_SEVERITY_RANK[flag.severity] > FLAG_SEVERITY_RANK[existing.severity]) {
      existing.severity = flag.severity;
    }
    if (!existing.messages.includes(flag.message)) existing.messages.push(flag.message);
    existing.evidence.push(flag.evidence);
  }
  return [...byKey.values()].sort(
    (a, b) => FLAG_SEVERITY_RANK[b.severity] - FLAG_SEVERITY_RANK[a.severity],
  );
}
