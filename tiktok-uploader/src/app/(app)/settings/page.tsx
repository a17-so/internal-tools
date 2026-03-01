'use client';

import { Copy, KeyRound } from 'lucide-react';
import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { toast } from 'sonner';

export default function SettingsPage() {
  const [name, setName] = useState('CLI Key');
  const [token, setToken] = useState<string | null>(null);

  const create = async () => {
    const res = await fetch('/api/auth/api-keys', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    });

    const data = await res.json();
    if (!res.ok) {
      toast.error(data.error || 'Failed to create key');
      return;
    }

    setToken(data.apiKey.token);
    toast.success('API key created');
  };

  const copy = async () => {
    if (!token) return;
    await navigator.clipboard.writeText(token);
    toast.success('Copied key');
  };

  return (
    <div className="space-y-4">
      <section className="panel p-5">
        <h2 className="text-2xl font-semibold">Settings</h2>
        <p className="text-muted-foreground">Generate API keys for CLI and automation workflows.</p>
      </section>

      <section className="panel max-w-2xl p-5">
        <div className="mb-4 flex items-center gap-2">
          <KeyRound className="h-4 w-4 text-indigo-600" />
          <h3 className="text-sm font-semibold text-slate-900">Create API Key</h3>
        </div>
        <div className="space-y-3">
          <div className="space-y-2">
            <Label>API Key Name</Label>
            <Input className="rounded-xl" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <Button className="rounded-xl" onClick={create}>Create API Key</Button>
          {token ? (
            <div className="rounded-xl border border-emerald-300 bg-emerald-50 p-3 text-sm">
              <p className="mb-2 font-semibold text-emerald-900">Copy this key now (shown once):</p>
              <pre className="overflow-x-auto whitespace-pre-wrap break-all rounded-lg border border-emerald-200 bg-white p-2 text-xs text-emerald-900">{token}</pre>
              <Button size="sm" variant="outline" className="mt-2 rounded-lg" onClick={copy}>
                <Copy className="h-3.5 w-3.5" />
                Copy
              </Button>
            </div>
          ) : null}
        </div>
      </section>
    </div>
  );
}
