'use client';

import { FormEvent, useState } from 'react';
import { useRouter } from 'next/navigation';
import { LockKeyhole, Sparkles } from 'lucide-react';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState(process.env.NEXT_PUBLIC_DEFAULT_LOGIN_EMAIL || '');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || 'Login failed');
      }

      toast.success('Logged in');
      router.replace('/');
      router.refresh();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden p-6">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,#d9e4ff,transparent_45%),radial-gradient(circle_at_bottom_right,#d0f1ff,transparent_50%),linear-gradient(180deg,#f8faff_0%,#edf3ff_55%,#f2fbff_100%)]" />
      <div className="relative z-10 grid w-full max-w-4xl gap-4 md:grid-cols-[1.2fr_1fr]">
        <section className="panel hidden p-6 md:block">
          <div className="mb-3 inline-flex items-center gap-2 rounded-full bg-indigo-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.09em] text-indigo-700">
            <Sparkles className="h-3.5 w-3.5" />
            Uploader V2
          </div>
          <h1 className="text-4xl font-semibold text-slate-900">Publishing control for high-volume batches</h1>
          <p className="mt-3 max-w-md text-slate-600">Run multi-account uploads, queue management, and failure recovery from one place with CLI parity.</p>
        </section>

        <Card className="panel border-0 shadow-none">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-xl">
              <LockKeyhole className="h-5 w-5 text-indigo-600" />
              Operator Login
            </CardTitle>
            <CardDescription>Sign in with your internal operator account.</CardDescription>
          </CardHeader>
          <form onSubmit={onSubmit}>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input id="email" className="rounded-xl" value={email} onChange={(e) => setEmail(e.target.value)} type="email" required />
              </div>
              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <Input id="password" className="rounded-xl" value={password} onChange={(e) => setPassword(e.target.value)} type="password" required />
              </div>
            </CardContent>
            <CardFooter>
              <Button className="w-full rounded-xl" disabled={loading}>{loading ? 'Signing in...' : 'Sign in'}</Button>
            </CardFooter>
          </form>
        </Card>
      </div>
    </main>
  );
}
