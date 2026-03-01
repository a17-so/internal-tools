'use client';

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

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold text-slate-900">Settings</h2>
        <p className="text-slate-600">Create API keys for CLI automation.</p>
      </div>

      <div className="max-w-md space-y-3 rounded-xl border border-slate-200 bg-white p-4">
        <div className="space-y-2">
          <Label>API Key Name</Label>
          <Input value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <Button onClick={create}>Create API Key</Button>
        {token ? (
          <div className="rounded border border-emerald-300 bg-emerald-50 p-3 text-sm">
            <p className="mb-2 font-semibold">Copy this key now (shown once):</p>
            <pre className="overflow-x-auto whitespace-pre-wrap break-all">{token}</pre>
          </div>
        ) : null}
      </div>
    </div>
  );
}
