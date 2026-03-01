'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { BarChart3, Clock3, History, Layers, LogOut, Send, Settings, Sparkles, Users } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

const navItems = [
  { href: '/', label: 'Dashboard', icon: BarChart3, hint: 'Overview and throughput' },
  { href: '/accounts', label: 'Accounts', icon: Users, hint: 'Connect platforms' },
  { href: '/compose', label: 'Compose', icon: Sparkles, hint: 'Build and queue posts' },
  { href: '/queue', label: 'Queue', icon: Clock3, hint: 'Dispatch and control jobs' },
  { href: '/history', label: 'History', icon: History, hint: 'Audit completed jobs' },
  { href: '/settings', label: 'Settings', icon: Settings, hint: 'Keys and integrations' },
];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();

  const onLogout = async () => {
    await fetch('/api/auth/logout', { method: 'POST' });
    router.replace('/login');
    router.refresh();
  };

  return (
    <div className="min-h-screen bg-muted/30">
      <div className="mx-auto grid min-h-screen max-w-[1400px] grid-cols-1 gap-4 px-3 py-4 md:grid-cols-[250px_minmax(0,1fr)] md:px-5 md:py-5">
        <aside className="panel flex flex-col overflow-hidden md:sticky md:top-5 md:h-[calc(100vh-2.5rem)]">
          <div className="border-b px-4 py-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">Internal Tools</p>
            <div className="mt-2 flex items-center gap-2">
              <div className="rounded-lg bg-primary p-2 text-primary-foreground">
                <Layers className="h-4 w-4" />
              </div>
              <div>
                <h1 className="text-lg font-semibold">Uploader</h1>
                <p className="text-xs text-muted-foreground">Multi-account control room</p>
              </div>
            </div>
          </div>

          <nav className="space-y-1 p-3">
            {navItems.map((item) => {
              const active = pathname === item.href;
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    'group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-all',
                    active
                      ? 'bg-primary text-primary-foreground'
                      : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                  )}
                >
                  <Icon className={cn('h-4 w-4', active ? 'text-primary-foreground' : 'text-muted-foreground group-hover:text-foreground')} />
                  <div className="min-w-0">
                    <p className="truncate">{item.label}</p>
                    <p className={cn('truncate text-[11px]', active ? 'text-primary-foreground/80' : 'text-muted-foreground/80')}>{item.hint}</p>
                  </div>
                </Link>
              );
            })}
          </nav>

          <div className="mx-3 mt-auto space-y-2 border-t py-3">
            <Button asChild className="w-full justify-start rounded-xl" size="sm">
              <Link href="/compose">
                <Send className="h-4 w-4" />
                New Batch
              </Link>
            </Button>
            <Button variant="outline" className="w-full justify-start rounded-xl" size="sm" onClick={onLogout}>
              <LogOut className="h-4 w-4" />
              Log out
            </Button>
          </div>
        </aside>

        <div className="min-w-0 space-y-4">
          <main>{children}</main>
        </div>
      </div>
    </div>
  );
}
