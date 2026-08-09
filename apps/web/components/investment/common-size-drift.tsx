'use client';

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { colors, fontSize, spacing } from '@crisol/ui';
import type { VerticalPoint } from '@crisol/types';

/**
 * La deriva de la estructura de márgenes (PHASE-44.22).
 *
 * El common-size ya estaba en la pestaña de Estados, como tabla de doce
 * partidas por ejercicio. Eso responde «¿cuánto pesó cada cosa?» y no responde
 * la pregunta para la que se inventó la vista: **¿la estructura se está
 * moviendo?** Doce series serían pared de colores —el techo son siete— así que
 * aquí van las CUATRO que cuentan la historia del margen, de arriba abajo de la
 * cuenta de resultados.
 *
 * Cuatro series obligan a etiqueta directa (el amarillo y el naranja ya
 * comparten pantalla en cualquier paleta), así que cada línea lleva su nombre
 * al final en vez de una leyenda que obligue a ir y volver.
 *
 * Un solo eje, siempre: son cuatro pesos sobre la MISMA base, así que comparten
 * escala por construcción. Dos ejes aquí sería inventar una comparación.
 */

/**
 * Las cuatro partidas, en el orden en que bajan por la cuenta de resultados, con
 * su hue FIJO: el color sigue a la partida, no a su posición en la lista, así
 * que una serie que desaparezca porque el emisor no la publica no repinta a las
 * demás.
 *
 * Los dos primeros colores fueron el cobre de la marca y su tono oscuro, y el
 * validador los tumbó: **ΔE 14,3 con visión normal**, por debajo del suelo de
 * 15. No es un problema de daltonismo —ahí también fallaban— sino de que
 * cualquiera los confunde, y eso no lo arregla una etiqueta. Con el morado en su
 * sitio, el peor par pasa a 17,1 (normal) y 9,6 (deuteranopía).
 */
const TRACKED: { item: string; label: string; color: string }[] = [
  { item: 'cogs', label: 'Coste de ventas', color: '#c4671f' },
  { item: 'sga_expense', label: 'Gastos generales', color: '#7b3fa0' },
  { item: 'ebit', label: 'EBIT', color: '#2a78d6' },
  { item: 'net_income', label: 'Resultado neto', color: '#2e7d32' },
];

export function CommonSizeDrift({ vertical }: { vertical: VerticalPoint[] }) {
  const overRevenue = vertical.filter((p) => p.base === 'revenue' && p.weight !== null);
  const years = [...new Set(overRevenue.map((p) => p.fiscal_year))].sort((a, b) => a - b);
  const tracked = TRACKED.filter((t) => overRevenue.some((p) => p.item === t.item));

  if (years.length < 2 || tracked.length === 0) {
    return (
      <p style={{ margin: 0, color: colors.textMuted, fontSize: fontSize.sm }}>
        Hacen falta al menos dos ejercicios con cuenta de resultados para ver la deriva.
      </p>
    );
  }

  const data = years.map((year) => {
    const row: Record<string, number | string> = { year: String(year) };
    for (const { item } of tracked) {
      const point = overRevenue.find((p) => p.fiscal_year === year && p.item === item);
      if (point?.weight != null) row[item] = Number(point.weight) * 100;
    }
    return row;
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.sm }}>
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={data} margin={{ top: 8, right: 116, bottom: 4, left: 0 }}>
          {/* Rejilla SÓLIDA y a un tono del fondo. Los demás charts de la app la
              llevan discontinua, que es ruido visual y además se lee como
              «umbral» o «proyección» cuando sólo es una guía. Aquí se estrena la
              regla; alinear los antiguos es una pasada aparte. */}
          <CartesianGrid stroke={colors.border} vertical={false} />
          <XAxis
            dataKey="year"
            tick={{ fill: colors.textMuted, fontSize: 11 }}
            axisLine={{ stroke: colors.border }}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: colors.textMuted, fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            width={44}
            tickFormatter={(v: number) => `${v.toFixed(0)}%`}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: colors.surface,
              border: `1px solid ${colors.border}`,
              borderRadius: 8,
              fontSize: 12,
            }}
            // Boundary con la API de Recharts: sus tipos son deliberadamente
            // laxos (`ValueType`), así que el estrechamiento se hace aquí, una
            // vez, en vez de repartirlo por el componente.
            formatter={(value, key) => [
              `${Number(value).toLocaleString('es-ES', { maximumFractionDigits: 1 })}%`,
              TRACKED.find((t) => t.item === String(key))?.label ?? String(key),
            ]}
            labelFormatter={(year: React.ReactNode) => `Ejercicio ${String(year)}`}
          />
          {tracked.map((serie) => (
            <Line
              key={serie.item}
              type="monotone"
              dataKey={serie.item}
              stroke={serie.color}
              strokeWidth={2}
              dot={{ r: 3, strokeWidth: 0, fill: serie.color }}
              activeDot={{ r: 5 }}
              // Etiqueta directa en el último punto: con cuatro series es
              // obligatoria, y ahorra el viaje a la leyenda en cada lectura.
              label={<DirectLabel label={serie.label} color={serie.color} years={years.length} />}
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
      <p style={{ margin: 0, color: colors.textMuted, fontSize: fontSize.xs, lineHeight: 1.5 }}>
        Cada partida como porcentaje de las ventas del mismo ejercicio. Lo que informa no es el
        nivel —depende del sector— sino el <strong>movimiento</strong>: un coste de ventas que sube
        tres años seguidos se come el margen aunque las ventas crezcan.
      </p>
    </div>
  );
}

/** Etiqueta al final de la línea. Recharts la llama por punto; sólo se pinta en
 *  el último para no repetir el nombre N veces. */
function DirectLabel(props: {
  label: string;
  color: string;
  years: number;
  index?: number;
  x?: number;
  y?: number;
}) {
  const { label, color, years, index, x, y } = props;
  if (index !== years - 1 || x === undefined || y === undefined) return null;
  return (
    <text x={x + 8} y={y + 4} fill={color} fontSize={11}>
      {label}
    </text>
  );
}
