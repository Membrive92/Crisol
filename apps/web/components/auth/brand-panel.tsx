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
          backgroundColor: 'rgba(255, 255, 255, 0.12)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#ffffff',
        }}
      >
        {icon}
      </div>
      <div>
        <div
          style={{
            fontSize: fontSize.md,
            fontWeight: fontWeight.semibold,
            color: '#ffffff',
            marginBottom: 2,
          }}
        >
          {title}
        </div>
        <div
          style={{
            fontSize: fontSize.sm,
            color: 'rgba(255, 255, 255, 0.78)',
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
        // Gradiente que tira del primario hacia un azul más profundo —
        // se mantiene legible en light y dark porque es una superficie
        // intencionalmente saturada.
        background: `linear-gradient(135deg, ${colors.primary} 0%, ${colors.primaryDark} 100%)`,
        color: '#ffffff',
        overflow: 'hidden',
      }}
    >
      {/* Decoración: dos círculos translúcidos que dan profundidad. */}
      <div
        aria-hidden="true"
        style={{
          position: 'absolute',
          top: -120,
          right: -120,
          width: 360,
          height: 360,
          borderRadius: '50%',
          background: 'rgba(255, 255, 255, 0.08)',
        }}
      />
      <div
        aria-hidden="true"
        style={{
          position: 'absolute',
          bottom: -160,
          left: -80,
          width: 280,
          height: 280,
          borderRadius: '50%',
          background: 'rgba(255, 255, 255, 0.06)',
        }}
      />

      <div style={{ position: 'relative', zIndex: 1 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: spacing.sm }}>
          <IconLogo size={36} />
          <span
            style={{
              fontSize: fontSize.xl,
              fontWeight: fontWeight.semibold,
              letterSpacing: '-0.01em',
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
          }}
        >
          Tus finanzas, privadas y locales.
        </h2>
        <p
          style={{
            margin: 0,
            fontSize: fontSize.md,
            color: 'rgba(255, 255, 255, 0.85)',
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
          color: 'rgba(255, 255, 255, 0.6)',
        }}
      >
        © {new Date().getFullYear()} Finanzas — open source, autoalojado.
      </div>
    </aside>
  );
}
