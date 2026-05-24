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
    // Las pestañas primarias del módulo son sólo dos: lectura (Análisis)
    // y datos (Transacciones). Importar y Tickets son flujos secundarios
    // de entrada de datos: viven como acciones/CTAs dentro de la página
    // Transacciones (no como tabs primarias). Mantienen sus rutas
    // dedicadas (`/personal-finance/imports`, `/.../receipts`) — sólo
    // dejan de competir con la lista en el chrome.
    sections: [
      { key: 'analysis', label: 'Análisis', path: `${PERSONAL_FINANCE_BASE}/analysis` },
      { key: 'transactions', label: 'Transacciones', path: `${PERSONAL_FINANCE_BASE}/transactions` },
      { key: 'budgets', label: 'Presupuestos', path: `${PERSONAL_FINANCE_BASE}/budgets` },
      { key: 'fixed-expenses', label: 'Gastos fijos', path: `${PERSONAL_FINANCE_BASE}/fixed-expenses` },
      { key: 'transfers', label: 'Transferencias', path: `${PERSONAL_FINANCE_BASE}/transfers` },
    ],
  },
  {
    // Módulo de deuda: hereda de personal-finance los accounts marcados
    // como `nature=liability` y construye encima KPIs de salud (DTI,
    // weighted APR, intereses YTD, time-to-payoff), evolución temporal
    // y lista de pasivos. Es top-level porque la vista funciona como
    // panel autónomo aunque las cuentas se siguen gestionando desde
    // Finanzas Domésticas.
    id: 'debt',
    label: 'Deuda',
    basePath: '/debt',
    enabled: true,
    sections: [],
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
