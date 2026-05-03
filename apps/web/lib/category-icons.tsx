'use client';

import type { ComponentType } from 'react';

import {
  BanknoteIcon,
  BriefcaseIcon,
  CarIcon,
  CoffeeIcon,
  CreditCardIcon,
  FolderIcon,
  GiftIcon,
  HeartPulseIcon,
  HomeIcon,
  PlaneIcon,
  ShoppingBagIcon,
  ShoppingCartIcon,
  TvIcon,
  UtensilsIcon,
  WifiIcon,
} from '@/components/ui/icons';

interface IconProps {
  size?: number | undefined;
}

type IconCmp = ComponentType<IconProps>;

/**
 * Diccionario nombre-de-categoría → icono. Se busca por:
 * 1) match exacto (case-insensitive),
 * 2) substring (la categoría contiene una clave),
 * 3) fallback: `FolderIcon`.
 *
 * Las claves son substrings comunes en español + inglés. Cuando se
 * habilite la columna `categories.icon` (PHASE-7.6 follow-up), este
 * mapeo seguirá vivo como fallback para categorías sin icono explícito.
 */
const CATEGORY_ICON_MAP: Record<string, IconCmp> = {
  // Hogar
  hogar: HomeIcon,
  casa: HomeIcon,
  housing: HomeIcon,
  alquiler: HomeIcon,
  rent: HomeIcon,
  mortgage: HomeIcon,
  hipoteca: HomeIcon,

  // Comida
  comida: UtensilsIcon,
  alimentación: UtensilsIcon,
  alimentacion: UtensilsIcon,
  groceries: ShoppingCartIcon,
  supermercado: ShoppingCartIcon,
  food: UtensilsIcon,
  grocery: ShoppingCartIcon,

  // Restauración
  restaurante: CoffeeIcon,
  restaurant: CoffeeIcon,
  dining: CoffeeIcon,
  café: CoffeeIcon,
  cafe: CoffeeIcon,
  coffee: CoffeeIcon,

  // Transporte
  transporte: CarIcon,
  transportation: CarIcon,
  gasolina: CarIcon,
  gas: CarIcon,
  fuel: CarIcon,
  uber: CarIcon,
  taxi: CarIcon,
  coche: CarIcon,
  car: CarIcon,

  // Viajes
  viaje: PlaneIcon,
  viajes: PlaneIcon,
  travel: PlaneIcon,
  vacaciones: PlaneIcon,
  flight: PlaneIcon,

  // Trabajo / ingresos
  trabajo: BriefcaseIcon,
  salario: BriefcaseIcon,
  nómina: BriefcaseIcon,
  nomina: BriefcaseIcon,
  ingreso: BriefcaseIcon,
  ingresos: BriefcaseIcon,
  income: BriefcaseIcon,
  payroll: BriefcaseIcon,
  freelance: BriefcaseIcon,

  // Salud / farmacia
  salud: HeartPulseIcon,
  health: HeartPulseIcon,
  medical: HeartPulseIcon,
  farmacia: HeartPulseIcon,
  pharmacy: HeartPulseIcon,
  medicina: HeartPulseIcon,

  // Compras
  compras: ShoppingBagIcon,
  shopping: ShoppingBagIcon,
  ropa: ShoppingBagIcon,
  clothing: ShoppingBagIcon,

  // Ocio / entretenimiento
  ocio: TvIcon,
  entretenimiento: TvIcon,
  entertainment: TvIcon,
  netflix: TvIcon,
  streaming: TvIcon,
  cine: TvIcon,
  movie: TvIcon,

  // Servicios / utilities
  servicios: WifiIcon,
  utilities: WifiIcon,
  internet: WifiIcon,
  luz: WifiIcon,
  agua: WifiIcon,
  gas_servicio: WifiIcon,

  // Regalos
  regalo: GiftIcon,
  regalos: GiftIcon,
  gift: GiftIcon,
  gifts: GiftIcon,

  // Suscripciones / banca
  suscripción: CreditCardIcon,
  suscripcion: CreditCardIcon,
  subscription: CreditCardIcon,
  banco: BanknoteIcon,
  bank: BanknoteIcon,
  finance: BanknoteIcon,
  banca: BanknoteIcon,
};

/** Devuelve el componente de icono más apropiado para un nombre de categoría. */
export function iconForCategoryName(name: string | null | undefined): IconCmp {
  if (!name) return FolderIcon;
  const normalized = name.trim().toLowerCase();
  if (!normalized) return FolderIcon;

  // Match exacto.
  const exact = CATEGORY_ICON_MAP[normalized];
  if (exact) return exact;

  // Match por substring (la categoría contiene la clave).
  for (const [key, Icon] of Object.entries(CATEGORY_ICON_MAP)) {
    if (normalized.includes(key)) return Icon;
  }

  return FolderIcon;
}

/**
 * Misma idea pero devuelve un icono según la `description` libre de la
 * transacción. Si no hay match por descripción, cae al icono de la
 * categoría. Útil en la lista "Actividad reciente" donde el title es
 * la descripción y la categoría puede no estar definida.
 */
export function iconForTransaction(
  description: string | null | undefined,
  categoryName: string | null | undefined,
): IconCmp {
  if (description) {
    const normalized = description.trim().toLowerCase();
    for (const [key, Icon] of Object.entries(CATEGORY_ICON_MAP)) {
      if (normalized.includes(key)) return Icon;
    }
  }
  return iconForCategoryName(categoryName);
}
