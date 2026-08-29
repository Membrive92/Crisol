'use client';

import { useState } from 'react';

import { colors, fontSize, fontWeight, groupFlags, radius, spacing } from '@crisol/ui';
import type { EngineFlag, FlagHelp, FlagSeverity } from '@crisol/types';
import type { GroupedFlag, ScoreHelpIndex } from '@crisol/ui';

import { HelpButton, helpTextStyle } from './help-toggle';

const SEVERITY: Record<FlagSeverity, { label: string; fg: string; bg: string }> = {
  red: { label: 'Grave', fg: colors.danger, bg: colors.dangerSoft },
  amber: { label: 'Atención', fg: colors.warning, bg: colors.warningSoft },
  info: { label: 'Informativa', fg: colors.textMuted, bg: colors.surfaceMuted },
};

export interface FlagListProps {
  flags: EngineFlag[];
  /** Qué decir cuando no hay ninguna. */
  emptyLabel?: string;
  /**
   * Fichas del motor. Sin ellas la tarjeta enseña el mensaje de la bandera y
   * nada más: el usuario sabe QUÉ ha saltado y no por qué le importa ni dónde
   * comprobarlo (PHASE-44.24.A.2).
   */
  help?: ScoreHelpIndex | undefined;
}

/** Las banderas del motor, con su mensaje en español y su evidencia desplegable. */
export function FlagList({
  flags,
  emptyLabel = 'Ninguna bandera encendida.',
  help,
}: FlagListProps) {
  const grouped = groupFlags(flags);
  if (grouped.length === 0) {
    return (
      <p style={{ margin: 0, color: colors.textMuted, fontSize: fontSize.sm }}>{emptyLabel}</p>
    );
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.sm }}>
      {grouped.map((flag) => (
        <FlagCard key={flag.key} flag={flag} ficha={help?.flag(flag.key)} />
      ))}
    </div>
  );
}

function FlagCard({ flag, ficha }: { flag: GroupedFlag; ficha?: FlagHelp | undefined }) {
  const [open, setOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const severity = SEVERITY[flag.severity];
  const occurrences = flag.evidence.length;

  return (
    <div
      style={{
        borderRadius: radius.md,
        backgroundColor: severity.bg,
        borderLeft: `3px solid ${severity.fg}`,
        padding: spacing.md,
        display: 'flex',
        flexDirection: 'column',
        gap: spacing.xs,
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: spacing.sm,
          flexWrap: 'wrap',
        }}
      >
        <span
          style={{
            color: severity.fg,
            fontSize: fontSize.xs,
            fontWeight: fontWeight.semibold,
            textTransform: 'uppercase',
            letterSpacing: '0.04em',
          }}
        >
          {severity.label}
          {flag.severity === 'info' ? ' · no puntúa en el veredicto' : ''}
          {ficha ? (
            <>
              {' '}
              <HelpButton
                label={ficha.label}
                help={ficha.what}
                open={helpOpen}
                onToggle={() => setHelpOpen((v) => !v)}
              />
            </>
          ) : null}
        </span>
        {occurrences > 1 ? (
          <span style={{ color: colors.textMuted, fontSize: fontSize.xs }}>
            {occurrences} apariciones
          </span>
        ) : null}
      </div>
      {flag.messages.map((message) => (
        <p key={message} style={{ margin: 0, color: colors.text, fontSize: fontSize.sm }}>
          {message}
        </p>
      ))}
      {/* Los tres campos separados: «por qué importa» se lee una vez y «dónde
          comprobarlo» es lo que se vuelve a consultar con las cuentas delante. */}
      {helpOpen && ficha ? (
        <div style={{ ...helpTextStyle, borderRadius: radius.sm, borderBottom: 'none' }}>
          <p style={{ margin: 0 }}>{ficha.what}</p>
          <p style={{ margin: `${spacing.xs}px 0 0` }}>
            <strong style={{ color: colors.text }}>Por qué importa: </strong>
            {ficha.why}
          </p>
          <p style={{ margin: `${spacing.xs}px 0 0` }}>
            <strong style={{ color: colors.text }}>Cómo se lee: </strong>
            {ficha.reading}
          </p>
          <p style={{ margin: `${spacing.xs}px 0 0` }}>
            <strong style={{ color: colors.text }}>Dónde comprobarlo: </strong>
            {ficha.how_to_verify}
          </p>
        </div>
      ) : null}

      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        style={{
          alignSelf: 'flex-start',
          background: 'none',
          border: 'none',
          padding: 0,
          color: colors.textMuted,
          fontSize: fontSize.xs,
          cursor: 'pointer',
          textDecoration: 'underline',
        }}
      >
        {open ? 'Ocultar evidencia' : 'Ver evidencia'}
      </button>
      {open ? (
        <pre
          style={{
            margin: 0,
            overflowX: 'auto',
            fontSize: fontSize.xs,
            color: colors.textMuted,
            backgroundColor: colors.surface,
            borderRadius: radius.sm,
            padding: spacing.sm,
          }}
        >
          {JSON.stringify(flag.evidence.length === 1 ? flag.evidence[0] : flag.evidence, null, 1)}
        </pre>
      ) : null}
    </div>
  );
}
