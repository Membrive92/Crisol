import type { ReactNode } from 'react';

import { AuthProvider } from '@/lib/auth-provider';

export const metadata = {
  title: 'Finanzas App',
  description: 'Finanzas personales multiportfolio con IA local',
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="es">
      <body
        style={{
          margin: 0,
          fontFamily:
            '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, sans-serif',
        }}
      >
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
