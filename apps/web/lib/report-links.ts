/**
 * Los enlaces de la pantalla de informe, como funciones PURAS (PHASE-44.24.G).
 *
 * Vivían inline en la ruta, donde no se pueden probar: la página es un cliente
 * con hooks de `next/navigation` y montarla exige un router falso. El resultado
 * fue que un gate de texto daba verde con el enlace roto — comprobaba que el
 * href se construía a partir de los params actuales, no que los CONSERVARA.
 */

import { locateMetric } from '@crisol/ui';

/**
 * A dónde lleva una señal del veredicto, o `null` si no lleva a ningún sitio.
 *
 * `null` significa «pinta texto, no enlace». Antes, una señal sin sitio (las 20
 * banderas y «stress») producía un enlace a la MISMA pestaña: recargaba la
 * página, cerraba el desglose que se estaba leyendo y no resaltaba nada — un
 * enlace que parecía roto porque lo estaba.
 *
 * Tres casos:
 * - La señal es una fila de otra pestaña → `?tab=…&sub=…&metric=<fila>`.
 * - La señal es una CARD de la misma pestaña (stress) → `#ancla`, que el
 *   navegador resuelve con scroll y sin recargar.
 * - La señal ya está a la vista (misma pestaña y sub) → `null`.
 *
 * @param current la pestaña y sub-pestaña en pantalla; `sub` vacío = la por
 *   defecto de esa pestaña.
 */
export function signalHrefFor(
  pathname: string,
  search: string,
  current: { tab: string; sub: string },
  signalKey: string,
): string | null {
  const target = locateMetric(signalKey);
  if (!target) return null;

  const sameTab = target.tab === current.tab;
  if (target.anchor) {
    // Un ancla no cambia de pestaña: si ya estás en ella, basta el hash.
    if (sameTab) return `#${target.anchor}`;
    const next = new URLSearchParams(search);
    next.set('tab', target.tab);
    if (target.sub) next.set('sub', target.sub);
    else next.delete('sub');
    next.delete('metric');
    return `${pathname}?${next.toString()}#${target.anchor}`;
  }

  const sameSub = (target.sub ?? null) === (current.sub || null);
  if (sameTab && sameSub) return null;

  const next = new URLSearchParams(search);
  next.set('tab', target.tab);
  if (target.sub) next.set('sub', target.sub);
  else next.delete('sub');
  next.set('metric', target.highlight ?? signalKey);
  return `${pathname}?${next.toString()}`;
}

/**
 * El enlace a «Cómo leer este informe», llevando de dónde se viene.
 *
 * La guía es una ruta aparte y no tenía vuelta: «Análisis» en la barra mandaba
 * al buscador vacío y sólo quedaba Atrás del navegador. El informe del que se
 * sale viaja en `back`, y la guía lo pinta como «← Volver al informe».
 */
export function guideHrefFor(pathname: string, search: string): string {
  const back = search ? `${pathname}?${search}` : pathname;
  return `/investments/analysis/guide?back=${encodeURIComponent(back)}`;
}

/**
 * La vuelta desde la guía, o `null` si no la hay o no es de fiar.
 *
 * Sólo se acepta una ruta INTERNA del propio informe: un `back` con esquema o
 * con otro host sería un redirect abierto, y uno a otra pantalla es un enlace
 * que no dice adónde va.
 */
export function guideBackHref(back: string | null): string | null {
  if (!back) return null;
  if (!back.startsWith('/investments/analysis/')) return null;
  if (back.startsWith('//')) return null;
  const path = back.split(/[?#]/, 1)[0] ?? '';
  const segments = path.split('/').filter(Boolean);
  // Exactamente `/investments/analysis/<id>`: ni la propia guía (un bucle), ni
  // `..`/`.` (que salen del informe), ni subrutas.
  if (segments.length !== 3) return null;
  const id = segments[2] ?? '';
  if (id === 'guide' || id === '..' || id === '.') return null;
  return back;
}

/**
 * La vuelta desde el modo dictamen: la misma ruta sin `print`.
 *
 * `window.close()` sólo cierra pestañas abiertas por script, y la del dictamen
 * nace sin opener (`noreferrer`): en Firefox no hacía nada. Un enlace funciona
 * en todos los casos, incluida la URL pegada a mano.
 */
export function reportHrefFor(pathname: string, search: string): string {
  const next = new URLSearchParams(search);
  next.delete('print');
  const query = next.toString();
  return query ? `${pathname}?${query}` : pathname;
}

/**
 * El enlace al dictamen imprimible.
 *
 * Conserva TODOS los parámetros actuales y añade `print=1`. Escribirlo como
 * `href="?print=1"` es una referencia relativa que sustituye la query entera
 * (RFC 3986 §5.3): se perdía el `?run=` y se imprimía el análisis más reciente
 * en vez del que estabas mirando, en un documento que existe para archivarse.
 */
export function printHrefFor(pathname: string, search: string): string {
  const next = new URLSearchParams(search);
  next.set('print', '1');
  return `${pathname}?${next.toString()}`;
}
