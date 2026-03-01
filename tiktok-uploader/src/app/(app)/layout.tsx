import { redirect } from 'next/navigation';
import AppShell from '@/components/layout/app-shell';
import { getOptionalAuth } from '@/lib/auth';

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const user = await getOptionalAuth();

  if (!user) {
    redirect('/login');
  }

  return <AppShell>{children}</AppShell>;
}
