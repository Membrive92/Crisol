import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// eslint-disable-next-line no-undef
const BACKEND_ORIGIN = process.env.BACKEND_ORIGIN ?? 'http://localhost:8001';

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
