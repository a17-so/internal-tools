'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import Uploader from '@/components/ui/uploader';

type User = {
  id: string;
  username: string;
  role: 'admin' | 'user';
};

type TikTokAccount = {
  id: string;
  userId: string;
  openId: string;
  displayName: string;
  source: 'oauth' | 'seeded';
  createdAt: string;
  updatedAt: string;
};

type MeResponse = {
  authenticated: boolean;
  user?: User;
  accounts?: TikTokAccount[];
};

type AuthMode = 'login' | 'register';

async function parseJsonSafe(response: Response) {
  try {
    return await response.json();
  } catch {
    return {};
  }
}

export default function AppShell() {
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState<User | null>(null);
  const [accounts, setAccounts] = useState<TikTokAccount[]>([]);
  const [authMode, setAuthMode] = useState<AuthMode>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const isAdmin = user?.role === 'admin';

  const loadSession = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/auth/me', { cache: 'no-store' });
      const data = (await parseJsonSafe(response)) as MeResponse;

      if (!response.ok || !data.authenticated || !data.user) {
        setUser(null);
        setAccounts([]);
        return;
      }

      setUser(data.user);
      setAccounts(data.accounts ?? []);
    } catch {
      setUser(null);
      setAccounts([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadSession();
  }, [loadSession]);

  const accountOptions = useMemo(
    () => accounts.map((account) => ({ id: account.id, displayName: account.displayName, openId: account.openId })),
    [accounts]
  );

  const submitAuth = async () => {
    if (!username.trim() || !password) {
      toast.error('Username and password are required');
      return;
    }

    setSubmitting(true);
    try {
      const response = await fetch(`/api/auth/${authMode}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: username.trim(), password }),
      });

      const data = await parseJsonSafe(response);
      if (!response.ok) {
        throw new Error(typeof data?.error === 'string' ? data.error : 'Authentication failed');
      }

      setPassword('');
      toast.success(authMode === 'login' ? 'Logged in' : 'Account created and logged in');
      await loadSession();
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Authentication failed';
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  };

  const logout = async () => {
    setSubmitting(true);
    try {
      await fetch('/api/auth/logout', { method: 'POST' });
      setUser(null);
      setAccounts([]);
      setPassword('');
      toast.success('Logged out');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-zinc-50 p-8 dark:bg-zinc-950">
        <p className="text-sm text-zinc-600 dark:text-zinc-400">Loading DraftUploader...</p>
      </main>
    );
  }

  if (!user) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-zinc-50 px-6 py-12 dark:bg-zinc-950">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>DraftUploader Auth</CardTitle>
            <CardDescription>Sign in with app credentials. No TikTok OAuth required for app login.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-2">
              <Button variant={authMode === 'login' ? 'default' : 'outline'} onClick={() => setAuthMode('login')} disabled={submitting}>
                Login
              </Button>
              <Button variant={authMode === 'register' ? 'default' : 'outline'} onClick={() => setAuthMode('register')} disabled={submitting}>
                Register
              </Button>
            </div>
            <div className="space-y-2">
              <Label htmlFor="app-username">Username</Label>
              <Input
                id="app-username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                disabled={submitting}
                placeholder="username"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="app-password">Password</Label>
              <Input
                id="app-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={submitting}
                placeholder="Minimum 8 characters"
              />
            </div>
          </CardContent>
          <CardFooter>
            <Button className="w-full" onClick={submitAuth} disabled={submitting}>
              {submitting ? 'Please wait...' : authMode === 'login' ? 'Login' : 'Create Account'}
            </Button>
          </CardFooter>
        </Card>
      </main>
    );
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-6xl flex-col gap-6 bg-zinc-50 px-6 py-10 dark:bg-zinc-950">
      <Card>
        <CardHeader>
          <CardTitle>{isAdmin ? 'Admin Portal' : 'User Portal'}</CardTitle>
          <CardDescription>
            Logged in as <strong>{user.username}</strong> ({user.role}). {isAdmin ? 'Admin can view and use all linked TikTok accounts.' : 'Users can only view and use their own linked TikTok accounts.'}
          </CardDescription>
        </CardHeader>
        <CardFooter className="flex gap-2">
          <Button asChild variant="outline">
            <Link href="/api/auth/tiktok">Connect TikTok Account</Link>
          </Button>
          <Button asChild variant="outline" disabled={accountOptions.length === 0}>
            <Link href={accountOptions.length ? `/analytics?accountId=${accountOptions[0].id}` : '/analytics'}>View Analytics</Link>
          </Button>
          <Button variant="destructive" onClick={logout} disabled={submitting}>Logout</Button>
        </CardFooter>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Account Management</CardTitle>
          <CardDescription>
            {isAdmin ? 'Admin view includes all users\' TikTok accounts plus seeded internal accounts.' : 'These TikTok accounts are linked to your user only.'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {accounts.length === 0 ? (
            <p className="text-sm text-zinc-600 dark:text-zinc-400">No TikTok accounts linked yet. Use Connect TikTok Account to add one.</p>
          ) : (
            <div className="space-y-2">
              {accounts.map((account) => (
                <div key={account.id} className="rounded-md border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-800">
                  <p className="font-medium">{account.displayName}</p>
                  <p className="text-xs text-zinc-500">open_id: {account.openId}</p>
                  {isAdmin ? <p className="text-xs text-zinc-500">owner user_id: {account.userId}</p> : null}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <div className="w-full">
        <Uploader accounts={accountOptions} />
      </div>
    </main>
  );
}
