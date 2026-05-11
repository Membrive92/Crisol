import type { ReactNode } from 'react';

import './globals.css';
import { AuthProvider } from '@/lib/auth-provider';
import { QueryProvider } from '@/lib/query-provider';
import { ThemeProvider } from '@/lib/theme-provider';

export const metadata = {
  title: 'Crisol',
  description: 'Crisol — finanzas personales multiportfolio con IA local',
  icons: {
    icon: [
      { url: '/favicon.svg', type: 'image/svg+xml' },
      { url: '/favicon.ico' },
    ],
    apple: '/apple-touch-icon.png',
  },
  appleWebApp: {
    title: 'Crisol',
  },
  manifest: '/manifest.webmanifest',
};

// Inline script que aplica el tema antes del primer paint para evitar
// flash de modo claro al cargar en modo oscuro. Soporta tres preferencias
// (light / dark / system); si no hay nada guardado, sigue al SO.
const themeBootstrapScript = `
(function() {
  try {
    var saved = localStorage.getItem('crisol_theme');
    var resolved;
    if (saved === 'light' || saved === 'dark') {
      resolved = saved;
    } else {
      resolved = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
    document.documentElement.dataset.theme = resolved;
  } catch (e) {
    document.documentElement.dataset.theme = 'light';
  }
})();
`;

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="es" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeBootstrapScript }} />
      </head>
      <body
        style={{
          margin: 0,
          fontFamily:
            '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, sans-serif',
        }}
      >
        <QueryProvider>
          <ThemeProvider>
            <AuthProvider>{children}</AuthProvider>
          </ThemeProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
