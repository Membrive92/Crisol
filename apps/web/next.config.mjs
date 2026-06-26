import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// eslint-disable-next-line no-undef
const BACKEND_ORIGIN = process.env.BACKEND_ORIGIN ?? 'http://localhost:8001';

// eslint-disable-next-line no-undef
const isProd = process.env.NODE_ENV === 'production';

// AUDIT-FIX (csp-default-src-none-en-toda-respuesta): la CSP del backend
// (`default-src 'none'`) protege las respuestas de la API, pero NO la SPA —
// el HTML/JS del frontend lo sirve Next.js, no FastAPI. Añadimos aquí las
// cabeceras de seguridad para las respuestas del frontend.
//
// Cuidado con la CSP en Next.js:
//   - En dev, React Fast Refresh y el runtime de Next requieren
//     `'unsafe-eval'` y websockets; una CSP estricta rompe el HMR.
//   - En prod, Next.js inyecta scripts inline para hidratación, así que sin
//     nonces hace falta `'unsafe-inline'` en `script-src`. Implementar nonces
//     por request exige un middleware dedicado (TODO: endurecer a nonce-based
//     cuando haya capacidad de probar el flujo completo de hidratación).
//
// Estrategia conservadora: cabeceras de bajo riesgo SIEMPRE; CSP razonable
// (no estricta) sólo en producción para no romper el dev server. `connect-src`
// incluye 'self' (el rewrite `/api/*` es same-origin) y, en dev, el websocket
// del HMR.
const cspProd = [
  "default-src 'self'",
  // 'unsafe-inline' por la hidratación de Next sin nonces (ver TODO arriba).
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  "connect-src 'self'",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "object-src 'none'",
].join('; ');

const securityHeaders = [
  { key: 'X-Content-Type-Options', value: 'nosniff' },
  { key: 'X-Frame-Options', value: 'DENY' },
  { key: 'Referrer-Policy', value: 'no-referrer' },
  // HSTS sólo tiene sentido sobre HTTPS; el navegador la ignora en HTTP, pero
  // la emitimos siempre para cubrir el caso de despliegue tras TLS. 2 años.
  {
    key: 'Strict-Transport-Security',
    value: 'max-age=63072000; includeSubDomains',
  },
  // CSP sólo en prod: en dev rompería Fast Refresh / HMR (necesita
  // 'unsafe-eval' + ws). En dev se omite y se confía en el resto de cabeceras.
  ...(isProd ? [{ key: 'Content-Security-Policy', value: cspProd }] : []),
];

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  outputFileTracingRoot: path.join(__dirname, '../..'),
  // El dev server cierra los rewrites/proxy a los 30s por defecto. La
  // inferencia local con qwen2.5vl:7b en CPU tarda 60-120s para un
  // ticket pero 3-5 min por página de extracto bancario. Para
  // /imports/preview con `force_vision=true` y 5 páginas el peor caso
  // ronda los 25 min en CPU. Damos 30 min de margen.
  experimental: {
    typedRoutes: true,
    proxyTimeout: 30 * 60 * 1000,
  },
  // Proxy /api/* a FastAPI para que la cookie httpOnly del refresh token
  // viaje same-origin. En producción este rewrite también funciona detrás
  // de un reverse proxy (Caddy / Traefik) — el origen es el del propio
  // dominio de la app, no el del backend.
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${BACKEND_ORIGIN}/:path*`,
      },
    ];
  },
  // Cabeceras de seguridad para TODAS las respuestas del frontend (ver bloque
  // `securityHeaders` arriba). No aplican a `/api/*` (esas las sirve FastAPI
  // con su propia CSP de defensa en profundidad).
  async headers() {
    return [
      {
        source: '/:path*',
        headers: securityHeaders,
      },
    ];
  },
  // Las rutas de secciones de personal-finance (`/transactions`, …) se han
  // movido bajo `/personal-finance/*` para reflejar la modularización del
  // dominio. Los 308 preservan el método HTTP y mantienen vivos los bookmarks
  // anteriores.
  //
  // El Dashboard ya NO vive bajo personal-finance: es un módulo de nivel
  // superior que agregará ingresos/gastos de todos los módulos verticales.
  // Por eso `/personal-finance/dashboard` redirige a `/dashboard`.
  async redirects() {
    const sections = ['transactions', 'imports', 'receipts'];
    return [
      ...sections.flatMap((section) => [
        {
          source: `/${section}`,
          destination: `/personal-finance/${section}`,
          permanent: true,
        },
        {
          source: `/${section}/:path*`,
          destination: `/personal-finance/${section}/:path*`,
          permanent: true,
        },
      ]),
      {
        source: '/personal-finance/dashboard',
        destination: '/dashboard',
        permanent: true,
      },
      {
        source: '/personal-finance/dashboard/:path*',
        destination: '/dashboard/:path*',
        permanent: true,
      },
    ];
  },
};

export default nextConfig;
