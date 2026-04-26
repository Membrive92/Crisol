import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// eslint-disable-next-line no-undef
const BACKEND_ORIGIN = process.env.BACKEND_ORIGIN ?? 'http://localhost:8001';

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  outputFileTracingRoot: path.join(__dirname, '../..'),
  experimental: {
    typedRoutes: true,
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
};

export default nextConfig;
