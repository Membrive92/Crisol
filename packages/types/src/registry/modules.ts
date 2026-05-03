import type { AppModule, ModuleId } from '../models/module';

export const PERSONAL_FINANCE_BASE = '/personal-finance';

export const MODULES: readonly AppModule[] = [
  {
    // Módulo global de agregación: combina ingresos y gastos de TODOS los
    // módulos verticales (personal-finance, crypto, etc.) en una vista
    // unificada. Para el MVP sólo hay personal-finance, pero el contrato
    // ya está listo: la página `/dashboard` consume los endpoints
    // `/dashboard/*` que el backend extenderá conforme lleguen nuevos
    // módulos con sus propias tablas.
    id: 'dashboard',
    label: 'Dashboard',
    basePath: '/dashboard',
    enabled: true,
    sections: [],
  },
  {
    id: 'personal-finance',
    label: 'Finanzas Domésticas',
    basePath: PERSONAL_FINANCE_BASE,
    enabled: true,
    sections: [
      { key: 'analysis', label: 'Análisis', path: `${PERSONAL_FINANCE_BASE}/analysis` },
      { key: 'transactions', label: 'Transacciones', path: `${PERSONAL_FINANCE_BASE}/transactions` },
      { key: 'imports', label: 'Importar', path: `${PERSONAL_FINANCE_BASE}/imports` },
      { key: 'receipts', label: 'Tickets', path: `${PERSONAL_FINANCE_BASE}/receipts` },
    ],
  },
  {
    id: 'crypto',
    label: 'Criptomonedas',
    basePath: '/crypto',
    enabled: false,
    sections: [],
  },
  {
    id: 'investments',
    label: 'Inversiones',
    basePath: '/investments',
    enabled: false,
    sections: [],
  },
  {
    id: 'real-estate',
    label: 'Inmuebles',
    basePath: '/real-estate',
    enabled: false,
    sections: [],
  },
] as const;

export const DEFAULT_MODULE_ID: ModuleId = 'dashboard';

export function getModule(id: ModuleId): AppModule | undefined {
  return MODULES.find((m) => m.id === id);
}

export function findModuleByPath(pathname: string): AppModule | undefined {
  return MODULES.find((m) => pathname === m.basePath || pathname.startsWith(`${m.basePath}/`));
}
