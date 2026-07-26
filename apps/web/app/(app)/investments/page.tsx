import type { Route } from 'next';
import { redirect } from 'next/navigation';

/** `/investments` redirige a la primera sección (Cartera). */
export default function InvestmentsIndexPage() {
  redirect('/investments/portfolio' as Route);
}
