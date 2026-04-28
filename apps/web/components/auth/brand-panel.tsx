'use client';

import { colors, fontSize, fontWeight, radius, spacing } from '@finanzas/ui';

import {
  IconBank,
  IconImport,
  IconLogo,
  IconRobot,
} from '@/components/auth/icons';

interface FeatureProps {
  icon: React.ReactNode;
  title: string;
  description: string;
}

function Feature({ icon, title, description }: FeatureProps) {
  return (
    <li
      style={{
        display: 'flex',
        gap: spacing.md,
        alignItems: 'flex-start',
      }}
    >
      <div
        style={{
          flexShrink: 0,
          width: 40,
          height: 40,
          borderRadius: radius.md,
          // Tinte primario suave (~14%) — adapta a light y dark sin
          // hardcodear rgba blanco.
          backgroundColor:
            'color-mix(in srgb, var(--color-primary) 14%, transparent)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: colors.primary,
        }}
      >
        {icon}
      </div>
      <div>
        <div
          style={{
            fontSize: fontSize.md,
            fontWeight: fontWeight.semibold,
            color: colors.text,
            marginBottom: 2,
          }}
        >
          {title}
        </div>
        <div
          style={{
            fontSize: fontSize.sm,
            color: colors.textMuted,
            lineHeight: 1.5,
          }}
        >
          {description}
        </div>
      </div>
    </li>
  );
}

export function BrandPanel() {
  return (
    <aside
      style={{
        flex: 1,
        minWidth: 0,
        position: 'relative',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        padding: spacing.xxl,
        // Panel calmado: usa las propias superficies del tema con un
        // gradiente sutil entre `surface` y `surface-muted` + un acento
        // primario radial en la esquina superior derecha. No compite con
        // el formulario por la atención.
        background: `
          radial-gradient(circle at top right,
            color-mix(in srgb, var(--color-primary) 16%, transparent) 0%,
            transparent 55%),
          linear-gradient(135deg, var(--color-surface) 0%, var(--color-surface-muted) 100%)
        `,
        color: colors.text,
        borderRight: `1px solid ${colors.border}`,
        overflow: 'hidden',
      }}
    >
      {/* Decoración: dos manchas suaves del primario para dar profundidad
          sin saturar. Visibles tanto en light como en dark. */}
      <div
        aria-hidden="true"
        style={{
          position: 'absolute',
          top: -140,
          right: -140,
          width: 380,
          height: 380,
          borderRadius: '50%',
          background:
            'color-mix(in srgb, var(--color-primary) 10%, transparent)',
          filter: 'blur(40px)',
        }}
      />
      <div
        aria-hidden="true"
        style={{
          position: 'absolute',
          bottom: -180,
          left: -100,
          width: 320,
          height: 320,
          borderRadius: '50%',
          background:
            'color-mix(in srgb, var(--color-primary) 6%, transparent)',
          filter: 'blur(50px)',
        }}
      />

      <div style={{ position: 'relative', zIndex: 1 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: spacing.sm }}>
          <span style={{ color: colors.primary, display: 'inline-flex' }}>
            <IconLogo size={36} />
          </span>
          <span
            style={{
              fontSize: fontSize.xl,
              fontWeight: fontWeight.semibold,
              letterSpacing: '-0.01em',
              color: colors.text,
            }}
          >
            Finanzas
          </span>
        </div>
      </div>

      <div style={{ position: 'relative', zIndex: 1 }}>
        <h2
          style={{
            margin: 0,
            fontSize: fontSize.xxl,
            fontWeight: fontWeight.bold,
            lineHeight: 1.15,
            letterSpacing: '-0.02em',
            marginBottom: spacing.sm,
            color: colors.text,
          }}
        >
          Tus finanzas, privadas y locales.
        </h2>
        <p
          style={{
            margin: 0,
            fontSize: fontSize.md,
            color: colors.textMuted,
            lineHeight: 1.5,
            maxWidth: 460,
            marginBottom: spacing.xl,
          }}
        >
          Monitoriza gastos e ingresos, importa extractos y captura tickets
          con IA local. Tus datos no salen de tu equipo.
        </p>

        <ul
          style={{
            listStyle: 'none',
            padding: 0,
            margin: 0,
            display: 'flex',
            flexDirection: 'column',
            gap: spacing.lg,
          }}
        >
          <Feature
            icon={<IconBank size={20} />}
            title="Transacciones y dashboard"
            description="Categoriza, filtra y visualiza tus gastos por mes y categoría."
          />
          <Feature
            icon={<IconImport size={20} />}
            title="Importa CSV, XLSX y PDF"
            description="Sube extractos del banco; la app los deduplica y mapea por ti."
          />
          <Feature
            icon={<IconRobot size={20} />}
            title="IA local para tickets"
            description="Foto al ticket, modelo en local extrae los datos. Tú confirmas."
          />
        </ul>
      </div>

      <div
        style={{
          position: 'relative',
          zIndex: 1,
          fontSize: fontSize.xs,
          color: colors.textSubtle,
        }}
      >
        © {new Date().getFullYear()} Finanzas — open source, autoalojado.
      </div>
    </aside>
  );
}
