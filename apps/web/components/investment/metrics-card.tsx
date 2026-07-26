'use client';

import { Card, CardTitle } from '@/components/ui/card';
import { spacing } from '@crisol/ui';
import type { MetricResult } from '@crisol/types';

import { findMetric, MetricRow } from './metric-row';

export interface MetricRowSpec {
  label: string;
  key: string;
  suffix?: string;
}

export function MetricsCard({
  title,
  metrics,
  year,
  rows,
}: {
  title: string;
  metrics: MetricResult[];
  year: number;
  rows: MetricRowSpec[];
}) {
  return (
    <Card style={{ display: 'flex', flexDirection: 'column', gap: spacing.sm }}>
      <CardTitle size="sm">{title}</CardTitle>
      <div>
        {rows.map((r) => (
          <MetricRow
            key={r.key}
            label={r.label}
            metric={findMetric(metrics, r.key, year)}
            suffix={r.suffix}
          />
        ))}
      </div>
    </Card>
  );
}
