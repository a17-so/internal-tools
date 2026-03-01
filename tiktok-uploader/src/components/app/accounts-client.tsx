'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';

export type AccountView = {
  id: string;
  provider: string;
  username: string | null;
  displayName: string | null;
  externalAccountId: string;
  tokenExpiresAt: string | null;
  capabilities: Array<{
    supportsDraftVideo: boolean;
    supportsDirectVideo: boolean;
    supportsPhotoSlideshow: boolean;
  }>;
};

export default function AccountsClient({ initialAccounts }: { initialAccounts: AccountView[] }) {
  const [accounts, setAccounts] = useState<AccountView[]>(initialAccounts);
  const [loading, setLoading] = useState(false);
  const [igUserId, setIgUserId] = useState('');
  const [igAccessToken, setIgAccessToken] = useState('');
  const [igDisplayName, setIgDisplayName] = useState('');
  const [ytAccessToken, setYtAccessToken] = useState('');
  const [ytDisplayName, setYtDisplayName] = useState('');
  const [fbPageId, setFbPageId] = useState('');
  const [fbAccessToken, setFbAccessToken] = useState('');
  const [fbDisplayName, setFbDisplayName] = useState('');

  const refresh = async () => {
    setLoading(true);
    const res = await fetch('/api/accounts');
    const data = await res.json();
    setAccounts(data.accounts || []);
    setLoading(false);
  };

  const hasAccounts = useMemo(() => accounts.length > 0, [accounts]);

  const removeAccount = async (id: string) => {
    const res = await fetch(`/api/accounts/${id}`, { method: 'DELETE' });
    if (!res.ok) {
      toast.error('Failed to remove account');
      return;
    }
    toast.success('Account removed');
    await refresh();
  };

  const connectInstagram = async () => {
    if (!igUserId.trim() || !igAccessToken.trim()) {
      toast.error('Instagram User ID and Access Token are required');
      return;
    }

    setLoading(true);
    const res = await fetch('/api/accounts/instagram/connect', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        instagramUserId: igUserId.trim(),
        accessToken: igAccessToken.trim(),
        displayName: igDisplayName.trim() || undefined,
      }),
    });

    const data = await res.json();
    if (!res.ok) {
      toast.error(data.error || 'Failed to connect Instagram');
      setLoading(false);
      return;
    }

    toast.success('Instagram account connected');
    setIgUserId('');
    setIgAccessToken('');
    setIgDisplayName('');
    await refresh();
  };

  const connectYouTube = async () => {
    if (!ytAccessToken.trim()) {
      toast.error('YouTube access token is required');
      return;
    }

    setLoading(true);
    const res = await fetch('/api/accounts/youtube/connect', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        accessToken: ytAccessToken.trim(),
        displayName: ytDisplayName.trim() || undefined,
      }),
    });

    const data = await res.json();
    if (!res.ok) {
      toast.error(data.error || 'Failed to connect YouTube');
      setLoading(false);
      return;
    }

    toast.success('YouTube account connected');
    setYtAccessToken('');
    setYtDisplayName('');
    await refresh();
  };

  const connectFacebook = async () => {
    if (!fbPageId.trim() || !fbAccessToken.trim()) {
      toast.error('Facebook Page ID and access token are required');
      return;
    }

    setLoading(true);
    const res = await fetch('/api/accounts/facebook/connect', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        pageId: fbPageId.trim(),
        accessToken: fbAccessToken.trim(),
        displayName: fbDisplayName.trim() || undefined,
      }),
    });

    const data = await res.json();
    if (!res.ok) {
      toast.error(data.error || 'Failed to connect Facebook');
      setLoading(false);
      return;
    }

    toast.success('Facebook account connected');
    setFbPageId('');
    setFbAccessToken('');
    setFbDisplayName('');
    await refresh();
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold text-slate-900">Accounts</h2>
          <p className="text-slate-600">Connect and manage TikTok + Instagram accounts.</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={() => void refresh()} disabled={loading}>Refresh</Button>
          <Button asChild>
            <Link href="/api/auth/tiktok">Connect TikTok</Link>
          </Button>
        </div>
      </div>

      {loading ? <p className="text-slate-500">Loading...</p> : null}

      {!loading && !hasAccounts ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center text-slate-500">
          No connected accounts yet.
        </div>
      ) : null}

      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-xl border border-slate-200 bg-white p-4 md:col-span-2">
          <h3 className="mb-2 text-sm font-semibold text-slate-900">Connect Instagram (token method)</h3>
          <p className="mb-4 text-xs text-slate-500">
            Use an Instagram Graph API token and professional IG user ID. Instagram currently supports direct video/Reels in this uploader.
          </p>
          <div className="grid gap-2 md:grid-cols-3">
            <input
              className="rounded-md border border-slate-300 px-3 py-2 text-sm"
              placeholder="Instagram User ID"
              value={igUserId}
              onChange={(e) => setIgUserId(e.target.value)}
            />
            <input
              className="rounded-md border border-slate-300 px-3 py-2 text-sm"
              placeholder="Display Name (optional)"
              value={igDisplayName}
              onChange={(e) => setIgDisplayName(e.target.value)}
            />
            <input
              className="rounded-md border border-slate-300 px-3 py-2 text-sm"
              placeholder="Access Token"
              value={igAccessToken}
              onChange={(e) => setIgAccessToken(e.target.value)}
            />
          </div>
          <div className="mt-3">
            <Button onClick={() => void connectInstagram()} disabled={loading}>Connect Instagram</Button>
          </div>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4 md:col-span-2">
          <h3 className="mb-2 text-sm font-semibold text-slate-900">Connect YouTube (token method)</h3>
          <p className="mb-4 text-xs text-slate-500">
            Use a YouTube Data API OAuth access token with channel scope. This uploader supports direct video upload (set to private).
          </p>
          <div className="grid gap-2 md:grid-cols-2">
            <input
              className="rounded-md border border-slate-300 px-3 py-2 text-sm"
              placeholder="Display Name (optional)"
              value={ytDisplayName}
              onChange={(e) => setYtDisplayName(e.target.value)}
            />
            <input
              className="rounded-md border border-slate-300 px-3 py-2 text-sm"
              placeholder="Access Token"
              value={ytAccessToken}
              onChange={(e) => setYtAccessToken(e.target.value)}
            />
          </div>
          <div className="mt-3">
            <Button onClick={() => void connectYouTube()} disabled={loading}>Connect YouTube</Button>
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 md:col-span-2">
          <h3 className="mb-2 text-sm font-semibold text-slate-900">Connect Facebook (token method)</h3>
          <p className="mb-4 text-xs text-slate-500">
            Use a Facebook Page access token and Page ID. This uploader supports direct video upload for connected pages.
          </p>
          <div className="grid gap-2 md:grid-cols-3">
            <input
              className="rounded-md border border-slate-300 px-3 py-2 text-sm"
              placeholder="Page ID"
              value={fbPageId}
              onChange={(e) => setFbPageId(e.target.value)}
            />
            <input
              className="rounded-md border border-slate-300 px-3 py-2 text-sm"
              placeholder="Display Name (optional)"
              value={fbDisplayName}
              onChange={(e) => setFbDisplayName(e.target.value)}
            />
            <input
              className="rounded-md border border-slate-300 px-3 py-2 text-sm"
              placeholder="Access Token"
              value={fbAccessToken}
              onChange={(e) => setFbAccessToken(e.target.value)}
            />
          </div>
          <div className="mt-3">
            <Button onClick={() => void connectFacebook()} disabled={loading}>Connect Facebook</Button>
          </div>
        </div>

        {accounts.map((account) => {
          const cap = account.capabilities[0];
          return (
            <div key={account.id} className="rounded-xl border border-slate-200 bg-white p-4">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-xs uppercase tracking-wider text-slate-500">{account.provider}</p>
                  <h3 className="text-lg font-semibold text-slate-900">{account.displayName || account.username || account.externalAccountId}</h3>
                  <p className="text-sm text-slate-600">{account.username ? `@${account.username}` : account.externalAccountId}</p>
                </div>
                <Button variant="outline" onClick={() => void removeAccount(account.id)}>Remove</Button>
              </div>
              {cap ? (
                <div className="mt-4 flex flex-wrap gap-2 text-xs">
                  <span className="rounded bg-slate-100 px-2 py-1">Draft video: {cap.supportsDraftVideo ? 'Yes' : 'No'}</span>
                  <span className="rounded bg-slate-100 px-2 py-1">Direct video: {cap.supportsDirectVideo ? 'Yes' : 'No'}</span>
                  <span className="rounded bg-slate-100 px-2 py-1">Slideshow: {cap.supportsPhotoSlideshow ? 'Yes' : 'No'}</span>
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}
