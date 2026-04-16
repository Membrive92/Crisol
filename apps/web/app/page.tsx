'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

import { useAuthStore } from '@finanzas/store';

export default function RootPage() {
  const router = useRouter();
  const { isAuthenticated, isHydrated } = useAuthStore();

  useEffect(() => {
    if (!isHydrated) return;
    router.replace(isAuthenticated ? '/home' : '/login');
  }, [isAuthenticated, isHydrated, router]);

  return null;
}
