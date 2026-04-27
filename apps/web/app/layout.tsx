import type { ReactNode } from 'react';

import './globals.css';
import { AuthProvider } from '@/lib/auth-provider';
import { QueryProvider } from '@/lib/query-provider';
import { ThemeProvider } from '@/lib/theme-provider';

export const metadata = {
  title: 'Finanzas App',
  description: 'Finanzas personales multiportfolio con IA local',
};

// Inline script que aplica el tema antes del primer paint para evitar
// flash de modo claro al cargar en modo oscuro: lee localStorage o
// `prefers-color-scheme` y setea `data-theme` en el <html>.
const themeBootstrapScript = `
(function() {
  try {
    var saved = localStorage.getItem('finanzas_theme');
    var theme = saved || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    document.documentElement.dataset.theme = theme;
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
