'use client';

import { useEffect, useId, useRef, useState } from 'react';

import {
  SEARCH_MIN_LENGTH,
  useAdoptSecurity,
  useResolveSecurity,
  useSecuritySearch,
} from '@crisol/services';
import { colors, fontSize, fontWeight, radius, spacing } from '@crisol/ui';
import type { SecuritySearchHit, TickerRequiredDetail } from '@crisol/types';

/**
 * Buscador estilo broker (PHASE-44.7, ampliado en PHASE-44.8 E2).
 *
 * Dos capas, las dos locales: el catálogo del usuario y el índice de los ~10.400
 * emisores que conoce la SEC. Antes sólo existía la primera, así que buscar por
 * nombre sólo encontraba lo que ya habías dado de alta y `Macdonald` daba cero.
 *
 * El mercado lo decide el SERVIDOR (E1): este componente ya no manda `exchange`.
 * Mandaba `'US'` —un país, no una plaza— y como la restricción única del
 * catálogo es `(ticker, exchange)`, el mismo valor podía acabar duplicado en dos
 * filas con dos ingestas y los lotes de cartera repartidos entre ambas. Al
 * elegir se devuelve la `listing_key` opaca que dio el buscador (E2), que además
 * conserva la plaza real del índice; resolver por ticker suelto la perdía y
 * guardaba MCD como `UNKNOWN`.
 *
 * **Combobox accesible (Entrega 3)**: `role="combobox"` con nombre accesible,
 * navegación completa por teclado (↑ ↓ Enter Esc Tab) y `aria-activedescendant`
 * — se puede usar entero sin ratón y un lector de pantalla anuncia la opción
 * activa. Las filas no seleccionables llevan `aria-disabled` **y el motivo
 * visible**: un `title` no lo lee nadie y en táctil no existe.
 *
 * `intent` decide qué es seleccionable, y no es cosmético: en Análisis, elegir
 * un valor que el motor no puede analizar (SPY: tiene CIK pero no presenta
 * 10-K) lleva a un callejón donde el mensaje manda a lanzar la ingesta que
 * acaba de fallar. En Cartera ese mismo valor es perfectamente válido — lo que
 * hace falta para registrar una compra es coste y divisa.
 */
/**
 * Extrae el detalle del 422 de un error del alta. Boundary de API: es el único
 * sitio del componente que mira dentro de la respuesta HTTP cruda.
 *
 * Devuelve el `TickerRequiredDetail` si es la degradación diseñada, el texto
 * del servidor si el detail es una cadena (p. ej. el cross-check de sufijo), o
 * `null` si no hay nada legible.
 */
function extractAdoptError(error: unknown): TickerRequiredDetail | string | null {
  if (typeof error !== 'object' || error === null) return null;
  const response = (error as { response?: { data?: { detail?: unknown } } }).response;
  const detail = response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (
    typeof detail === 'object' &&
    detail !== null &&
    (detail as { code?: unknown }).code === 'ticker_required'
  ) {
    return detail as TickerRequiredDetail;
  }
  return null;
}

/** Oculta visualmente sin sacar el elemento del árbol de accesibilidad. */
const visuallyHidden = {
  position: 'absolute' as const,
  width: 1,
  height: 1,
  padding: 0,
  margin: -1,
  overflow: 'hidden' as const,
  clip: 'rect(0 0 0 0)',
  whiteSpace: 'nowrap' as const,
  border: 0,
};

export function SecuritySearch({
  onSelect,
  placeholder = 'Ticker o nombre (ej. MCD, Johnson & Johnson)',
  intent = 'portfolio',
  label = 'Buscar valor',
}: {
  onSelect: (securityId: string) => void;
  placeholder?: string;
  /** `analysis` deshabilita lo que el motor no puede analizar; `portfolio` lo
   *  acepta todo (una posición sólo necesita coste y divisa). */
  intent?: 'analysis' | 'portfolio';
  /** Nombre accesible del combobox. Se pinta oculto visualmente. */
  label?: string;
}) {
  const baseId = useId();
  const listId = `${baseId}-list`;
  const inputRef = useRef<HTMLInputElement>(null);
  const [activeIndex, setActiveIndex] = useState(0);
  const [q, setQ] = useState('');
  const search = useSecuritySearch(q);
  const resolve = useResolveSecurity();
  const adopt = useAdoptSecurity();
  const query = q.trim();
  const results = search.data?.results ?? [];
  const notice = search.data?.notice ?? null;
  const indexReady = search.data?.index_ready ?? true;
  const directorySeededAt = search.data?.directory_seeded_at ?? null;
  const busy = resolve.isPending || adopt.isPending;
  const failed = resolve.isError || adopt.isError;
  const open = query.length >= SEARCH_MIN_LENGTH;

  /** Por qué NO se puede elegir esta fila, o `null` si sí se puede. */
  function blockedReason(hit: SecuritySearchHit): string | null {
    if (intent !== 'analysis' || hit.analysis_available) return null;
    return hit.analysis_reason ?? 'Este valor no se puede analizar.';
  }

  const activeHit = results[activeIndex];

  /**
   * La opción activa se arrastra a la vista al navegar con el teclado.
   *
   * `aria-activedescendant` le dice al lector de pantalla cuál es la activa,
   * pero al ojo no le dice nada: sin esto, bajar con ↓ por veinte resultados
   * movía una selección invisible. `block: 'nearest'` desplaza lo mínimo, así
   * que la lista no salta cuando la activa ya se ve.
   *
   * El `?.` de `scrollIntoView` no es defensa contra el DOM: jsdom no lo
   * implementa, y sin él los tests del combobox revientan (misma familia que
   * `Blob.text()`, lección PHASE-4.2).
   */
  const activeOptionRef = useRef<HTMLLIElement>(null);
  useEffect(() => {
    activeOptionRef.current?.scrollIntoView?.({ block: 'nearest' });
  }, [activeIndex]);

  /** La degradación del alta ext: (PHASE-44.14): el proveedor no reconoce el
   *  ISIN y el servidor pide el ticker con la identidad pre-rellenada. */
  const [tickerPrompt, setTickerPrompt] = useState<{
    listingKey: string;
    detail: TickerRequiredDetail;
  } | null>(null);
  const [manualTicker, setManualTicker] = useState('');
  /** Mensaje del servidor cuando el alta se para con motivo (p. ej. el sufijo
   *  no casa con la plaza). Más útil que el genérico. */
  const [serverMessage, setServerMessage] = useState<string | null>(null);

  async function adoptKey(listingKey: string, ticker?: string): Promise<void> {
    setServerMessage(null);
    try {
      const body = ticker ? { listing_key: listingKey, ticker } : { listing_key: listingKey };
      const security = await adopt.mutateAsync(body);
      setTickerPrompt(null);
      setManualTicker('');
      onSelect(security.id);
    } catch (error) {
      const extracted = extractAdoptError(error);
      if (typeof extracted === 'string') {
        setServerMessage(extracted);
      } else if (extracted !== null) {
        setTickerPrompt({ listingKey, detail: extracted });
      }
      // Sin detail legible: el flag genérico `failed` ya pinta su mensaje.
    }
  }

  async function pick(hit: SecuritySearchHit): Promise<void> {
    if (hit.id) {
      onSelect(hit.id);
      return;
    }
    await adoptKey(hit.listing_key);
  }

  async function resolveTyped(): Promise<void> {
    if (!query) return;
    const security = await resolve.mutateAsync({ ticker: query.toUpperCase() });
    onSelect(security.id);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>): void {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, Math.max(results.length - 1, 0)));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === 'Enter') {
      // Enter sobre una fila bloqueada no hace nada — ni elige ni cierra. El
      // motivo ya está visible en la propia fila; tragarse la pulsación en
      // silencio sería peor que no poder pulsarla.
      if (open && activeHit && !blockedReason(activeHit)) {
        e.preventDefault();
        void pick(activeHit);
      }
    } else if (e.key === 'Escape') {
      if (q) {
        e.preventDefault();
        changeQuery('');
      }
    }
  }

  /**
   * Cambiar la búsqueda descarta el formulario de ticker manual y el mensaje
   * del servidor.
   *
   * Sin esto quedan pegados a la consulta anterior: el formulario seguiría en
   * pantalla mientras buscas otra cosa, y pulsar «Añadir» daría de alta el
   * listing que ya no estás mirando.
   */
  function changeQuery(next: string): void {
    setQ(next);
    setActiveIndex(0);
    setTickerPrompt(null);
    setManualTicker('');
    setServerMessage(null);
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.sm }}>
      {/* El nombre accesible va en un `<label>` oculto y no en un
          `aria-label`: así el campo sigue siendo enfocable pulsando el texto si
          algún día se decide mostrarlo, y no hay dos fuentes del nombre. */}
      <label htmlFor={baseId} style={visuallyHidden}>
        {label}
      </label>
      <input
        ref={inputRef}
        id={baseId}
        type="text"
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={
          open && activeHit ? `${baseId}-opt-${activeIndex}` : undefined
        }
        autoComplete="off"
        value={q}
        onChange={(e) => changeQuery(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        style={{
          padding: `${spacing.sm}px ${spacing.md}px`,
          borderRadius: radius.md,
          border: `1px solid ${colors.border}`,
          backgroundColor: colors.surface,
          color: colors.text,
          fontSize: fontSize.md,
          outlineColor: colors.primary,
        }}
      />
      {serverMessage ? (
        <span style={{ color: colors.danger, fontSize: fontSize.sm }}>{serverMessage}</span>
      ) : failed && !tickerPrompt ? (
        <span style={{ color: colors.danger, fontSize: fontSize.sm }}>
          No se pudo resolver el valor. Comprueba el ticker.
        </span>
      ) : null}
      {tickerPrompt ? (
        // Degradación diseñada del alta ext:: el proveedor de precios no
        // reconoce el ISIN. La identidad ya la tiene el directorio (viene
        // pre-rellenada del servidor); sólo falta el símbolo local.
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (manualTicker.trim()) {
              void adoptKey(tickerPrompt.listingKey, manualTicker.trim().toUpperCase());
            }
          }}
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: spacing.sm,
            border: `1px solid ${colors.border}`,
            borderRadius: radius.md,
            backgroundColor: colors.surface,
            padding: spacing.md,
          }}
        >
          <span style={{ color: colors.text, fontSize: fontSize.sm }}>
            <strong>{tickerPrompt.detail.prefill.name}</strong> ·{' '}
            {tickerPrompt.detail.prefill.mic} · {tickerPrompt.detail.prefill.currency} ·{' '}
            {tickerPrompt.detail.prefill.isin}
          </span>
          <span style={{ color: colors.textSubtle, fontSize: fontSize.xs }}>
            {tickerPrompt.detail.message}
          </span>
          <div style={{ display: 'flex', gap: spacing.sm }}>
            <input
              value={manualTicker}
              onChange={(e) => setManualTicker(e.target.value)}
              placeholder="Símbolo local (ej. ITX)"
              style={{
                flex: 1,
                padding: `${spacing.xs}px ${spacing.sm}px`,
                borderRadius: radius.sm,
                border: `1px solid ${colors.border}`,
                backgroundColor: colors.surface,
                color: colors.text,
                fontSize: fontSize.sm,
              }}
            />
            <button
              type="submit"
              disabled={busy || !manualTicker.trim()}
              style={{
                padding: `${spacing.xs}px ${spacing.md}px`,
                borderRadius: radius.sm,
                border: 'none',
                backgroundColor: colors.primary,
                color: colors.onPrimary,
                fontSize: fontSize.sm,
                fontWeight: fontWeight.semibold,
                cursor: 'pointer',
              }}
            >
              {adopt.isPending ? 'Validando…' : 'Añadir'}
            </button>
          </div>
        </form>
      ) : null}
      {/* Con una sola letra no se busca (traería medio catálogo), pero callarse
          es peor: teclear y no ver NADA se lee como "está roto". */}
      {query.length > 0 && query.length < SEARCH_MIN_LENGTH ? (
        <span style={{ color: colors.textSubtle, fontSize: fontSize.xs }}>
          Escribe al menos {SEARCH_MIN_LENGTH} caracteres.
        </span>
      ) : null}
      {open ? (
        <ul
          id={listId}
          role="listbox"
          aria-label={label}
          style={{
            listStyle: 'none',
            margin: 0,
            padding: 0,
            border: `1px solid ${colors.border}`,
            borderRadius: radius.md,
            backgroundColor: colors.surface,
            // Con `limit=20` la lista puede ocupar más que la ventana, y
            // entonces bajar con ↓ mueve una selección que no se ve. Acotarla y
            // arrastrar la activa a la vista son la misma corrección.
            maxHeight: 320,
            overflowY: 'auto',
          }}
        >
          {results.map((hit, index) => {
            const blocked = blockedReason(hit);
            const active = index === activeIndex;
            return (
            <li
              key={hit.listing_key}
              id={`${baseId}-opt-${index}`}
              ref={active ? activeOptionRef : undefined}
              role="option"
              aria-selected={active}
              aria-disabled={blocked !== null}
              onMouseEnter={() => setActiveIndex(index)}
              onClick={() => {
                if (!blocked && !busy) void pick(hit);
              }}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: spacing.md,
                padding: `${spacing.sm}px ${spacing.md}px`,
                borderBottom: `1px solid ${colors.border}`,
                backgroundColor: active ? colors.surfaceMuted : 'transparent',
                cursor: blocked ? 'not-allowed' : 'pointer',
                opacity: blocked ? 0.6 : 1,
              }}
            >
              <span style={{ color: colors.text, fontSize: fontSize.sm }}>
                {/* Las filas del directorio no llevan ticker (FIRDS no lo
                    publica; el símbolo real lo pone el alta): se identifican
                    por nombre, plaza, divisa e ISIN. */}
                {hit.ticker ? <strong>{hit.ticker} · </strong> : null}
                {hit.name}
                {hit.exchange_label ? (
                  <span style={{ color: colors.textSubtle }}> · {hit.exchange_label}</span>
                ) : null}
                {!hit.ticker && hit.currency ? (
                  <span style={{ color: colors.textSubtle }}> · {hit.currency}</span>
                ) : null}
                {!hit.ticker && hit.isin ? (
                  <span style={{ color: colors.textSubtle, fontSize: fontSize.xs }}>
                    {' '}
                    · {hit.isin}
                  </span>
                ) : null}
                {blocked ? (
                  // El motivo VISIBLE, no en un `title`: en táctil el title no
                  // existe y con lector de pantalla llega tarde. Es la mitad
                  // del porqué de que la fila esté apagada.
                  <span
                    style={{
                      display: 'block',
                      color: colors.textSubtle,
                      fontSize: fontSize.xs,
                      marginTop: 2,
                      lineHeight: 1.4,
                    }}
                  >
                    {blocked}
                  </span>
                ) : null}
              </span>
              {!hit.analysis_available ? (
                // "sin CIK" era jerga: al usuario no le dice nada. Lo que
                // importa es qué puede hacer con la fila.
                <span style={{ color: colors.textSubtle, fontSize: fontSize.xs }}>
                  sólo cartera
                </span>
              ) : !hit.in_catalog ? (
                // La fila viene del índice de la SEC: todavía no es un valor del
                // catálogo. Decirlo evita que "no lo tengo" se lea como un fallo
                // cuando el alta tarde un segundo en resolverse contra EDGAR.
                <span style={{ color: colors.textSubtle, fontSize: fontSize.xs }}>añadir</span>
              ) : null}
            </li>
            );
          })}
          {results.length === 0 && search.isFetching ? (
            // Sin esto, mientras llega la respuesta se pinta la escotilla de
            // EDGAR con la consulta a medio teclear, como si no hubiera nada.
            <li
              style={{
                padding: `${spacing.sm}px ${spacing.md}px`,
                color: colors.textSubtle,
                fontSize: fontSize.sm,
              }}
            >
              Buscando…
            </li>
          ) : null}
          {results.length === 0 && !search.isFetching && notice ? (
            // Cero resultados para «ITX» no significa «esa empresa no existe»,
            // sino «no es un emisor de la SEC». Un desplegable en blanco dice lo
            // primero, que es falso.
            <li
              style={{
                padding: `${spacing.sm}px ${spacing.md}px`,
                borderBottom: `1px solid ${colors.border}`,
                color: colors.textSubtle,
                fontSize: fontSize.xs,
                lineHeight: 1.5,
              }}
            >
              {notice}
            </li>
          ) : null}
          {results.length === 0 && !search.isFetching && directorySeededAt === null ? (
            // Directorio UE/UK vacío: cero resultados europeos sin sembrar
            // significa «no se ha mirado», no «no cotiza en Europa».
            <li
              style={{
                padding: `${spacing.sm}px ${spacing.md}px`,
                borderBottom: `1px solid ${colors.border}`,
                color: colors.textSubtle,
                fontSize: fontSize.xs,
                lineHeight: 1.5,
              }}
            >
              El directorio de valores europeos no está sembrado
              (`seed_listing_directory`), así que sólo se ha buscado en la SEC y en tu
              catálogo.
            </li>
          ) : null}
          {results.length === 0 && !search.isFetching && !indexReady ? (
            // El índice no cargó: sin esto, «0 resultados» se presentaría como
            // «no hay coincidencias», que es una afirmación que no se puede
            // hacer cuando no se ha llegado a mirar.
            <li
              style={{
                padding: `${spacing.sm}px ${spacing.md}px`,
                borderBottom: `1px solid ${colors.border}`,
                color: colors.textSubtle,
                fontSize: fontSize.xs,
                lineHeight: 1.5,
              }}
            >
              El listado de emisores de la SEC no está disponible ahora mismo, así que sólo se ha
              buscado en tu catálogo.
            </li>
          ) : null}
          {results.length === 0 && !search.isFetching ? (
            <li>
            <button
              type="button"
              onClick={() => void resolveTyped()}
              disabled={busy}
              style={{
                display: 'block',
                width: '100%',
                padding: `${spacing.sm}px ${spacing.md}px`,
                border: 'none',
                backgroundColor: 'transparent',
                color: colors.primary,
                fontSize: fontSize.sm,
                fontWeight: fontWeight.semibold,
                cursor: 'pointer',
                textAlign: 'left',
              }}
            >
              {/* "Analizar" era falso en Cartera, donde lo que se está haciendo
                  es elegir el valor de una compra. "Traer" describe lo que hace
                  la acción —dar de alta el valor desde la SEC— y es cierto en las
                  dos pantallas. */}
              {busy ? 'Buscando en EDGAR…' : `Traer «${query.toUpperCase()}» de EDGAR`}
            </button>
            </li>
          ) : null}
        </ul>
      ) : null}
    </div>
  );
}
