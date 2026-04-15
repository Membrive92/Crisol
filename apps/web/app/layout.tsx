import type { ReactNode } from 'react';

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
        {children}
      </body>
    </html>
  );
}
