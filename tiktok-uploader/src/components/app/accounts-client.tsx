'use client';

import { useMemo, useState } from 'react';
import { AlertTriangle, CheckCircle2, KeyRound, RefreshCw, ShieldAlert, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';

export type AccountView = {
  id: string;
  provider: string;
  username: string | null;
  displayName: string | null;
  externalAccountId: string;
  tokenExpiresAt: string | null;
  health?: {
    needsReauth: boolean;
    expiresSoon: boolean;
    tokenExpiresAt: string | null;
    refreshExpiresAt: string | null;
    message: string | null;
  };
  capabilities: Array<{
    supportsDraftVideo: boolean;
    supportsDirectVideo: boolean;
    supportsPhotoSlideshow: boolean;
  }>;
};

const providerOptions = ['all', 'tiktok', 'instagram', 'youtube', 'facebook'];

type AccountsClientProps = {
  initialAccounts: AccountView[];
  initialError?: string | null;
  oauthConfig?: {
    instagram: boolean;
  };
};

function mapErrorMessage(error: string | null | undefined) {
  if (!error) return null;
  if (error === 'InstagramOAuthNotConfigured') {
    return 'Instagram OAuth is not configured. Set INSTAGRAM_APP_ID + INSTAGRAM_APP_SECRET (or FACEBOOK_APP_ID + FACEBOOK_APP_SECRET).';
  }
  if (error === 'MissingCode') return 'OAuth callback returned without an authorization code.';
  if (error === 'OAuthFailed') return 'OAuth flow failed. Reconnect and try again.';
  return decodeURIComponent(error.replace(/\+/g, ' '));
}

export default function AccountsClient({ initialAccounts, initialError, oauthConfig }: AccountsClientProps) {
  const [accounts, setAccounts] = useState<AccountView[]>(initialAccounts);
  const [loading, setLoading] = useState(false);
  const [providerFilter, setProviderFilter] = useState('all');
  const [igUserId, setIgUserId] = useState('');
  const [igAccessToken, setIgAccessToken] = useState('');
  const [igDisplayName, setIgDisplayName] = useState('');
  const [ytAccessToken, setYtAccessToken] = useState('');
  const [ytDisplayName, setYtDisplayName] = useState('');
  const [fbPageId, setFbPageId] = useState('');
  const [fbAccessToken, setFbAccessToken] = useState('');
  const [fbDisplayName, setFbDisplayName] = useState('');
  const accountPageError = mapErrorMessage(initialError);

  const refresh = async () => {
    setLoading(true);
    const res = await fetch('/api/accounts');
    const data = await res.json();
    setAccounts(data.accounts || []);
    setLoading(false);
  };

  const filteredAccounts = useMemo(() => {
    if (providerFilter === 'all') return accounts;
    return accounts.filter((account) => account.provider === providerFilter);
  }, [accounts, providerFilter]);

  const warningAccounts = useMemo(
    () => accounts.filter((a) => a.health?.needsReauth || a.health?.expiresSoon),
    [accounts]
  );

  const accountTitle = (account: AccountView) => account.displayName || (account.username ? `@${account.username}` : 'Connected account');
  const accountSubtext = (account: AccountView) => account.username ? `@${account.username}` : `id:${account.externalAccountId.slice(-10)}`;

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
    <div className="space-y-4">
      <section className="panel p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-2xl font-semibold text-slate-900">Accounts</h2>
            <p className="text-slate-600">Connect channels once, then target them in compose and CLI.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" className="rounded-xl" onClick={() => void refresh()} disabled={loading}>
              <RefreshCw className="h-4 w-4" />
              Refresh
            </Button>
            <Button asChild className="rounded-xl">
              <a href="/api/auth/tiktok">Connect TikTok</a>
            </Button>
            {oauthConfig?.instagram ? (
              <Button asChild variant="outline" className="rounded-xl">
                <a href="/api/auth/instagram">OAuth Instagram</a>
              </Button>
            ) : (
              <Button variant="outline" className="rounded-xl" disabled>
                OAuth Instagram (not configured)
              </Button>
            )}
            <Button asChild variant="outline" className="rounded-xl">
              <a href="/api/auth/youtube">OAuth YouTube</a>
            </Button>
            <Button asChild variant="outline" className="rounded-xl">
              <a href="/api/auth/facebook">OAuth Facebook</a>
            </Button>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          <span className="pill">Total: {accounts.length}</span>
          <span className="pill">Needs Reauth: {warningAccounts.filter((a) => a.health?.needsReauth).length}</span>
          <span className="pill">Expiring Soon: {warningAccounts.filter((a) => a.health?.expiresSoon).length}</span>
        </div>
      </section>

      {accountPageError ? (
        <section className="panel border-rose-200 bg-rose-50/90 p-4">
          <div className="flex items-center gap-2 text-rose-800">
            <AlertTriangle className="h-4 w-4" />
            <p className="text-sm font-semibold">Connection error</p>
          </div>
          <p className="mt-1 text-sm text-rose-900">{accountPageError}</p>
        </section>
      ) : null}

      {warningAccounts.length ? (
        <section className="panel border-amber-200 bg-amber-50/90 p-4">
          <div className="mb-2 flex items-center gap-2 text-amber-800">
            <ShieldAlert className="h-4 w-4" />
            <p className="text-sm font-semibold">Authentication attention needed</p>
          </div>
          <div className="space-y-1 text-sm text-amber-900">
            {warningAccounts.map((a) => (
              <p key={`warn-${a.id}`}>{a.provider} · {accountTitle(a)}: {a.health?.message}</p>
            ))}
          </div>
        </section>
      ) : null}

      <section className="panel p-4">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-semibold text-slate-900">Connected accounts</h3>
          <div className="flex gap-1 rounded-xl border border-slate-200 bg-slate-50 p-1">
            {providerOptions.map((provider) => (
              <button
                key={provider}
                className={`rounded-lg px-2.5 py-1 text-xs font-medium ${providerFilter === provider ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600 hover:text-slate-900'}`}
                onClick={() => setProviderFilter(provider)}
              >
                {provider}
              </button>
            ))}
          </div>
        </div>

        {loading ? <p className="text-sm text-slate-500">Loading...</p> : null}
        {!loading && !filteredAccounts.length ? (
          <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50/70 p-8 text-center text-slate-500">No accounts in this filter.</div>
        ) : null}

        <div className="grid gap-3 lg:grid-cols-2">
          {filteredAccounts.map((account) => {
            const cap = account.capabilities[0];
            const hasWarning = Boolean(account.health?.needsReauth || account.health?.expiresSoon);
            return (
              <article key={account.id} className="rounded-2xl border border-slate-200 bg-white/90 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.08em] text-slate-500">{account.provider}</p>
                    <h4 className="mt-1 text-lg font-semibold text-slate-900">{accountTitle(account)}</h4>
                    <p className="text-sm text-slate-500">{accountSubtext(account)}</p>
                  </div>
                  <Button variant="outline" size="sm" className="rounded-lg" onClick={() => void removeAccount(account.id)}>
                    <Trash2 className="h-3.5 w-3.5" />
                    Remove
                  </Button>
                </div>

                <div className="mt-3 flex flex-wrap gap-2 text-xs">
                  <span className="pill">Draft: {cap?.supportsDraftVideo ? 'Yes' : 'No'}</span>
                  <span className="pill">Direct: {cap?.supportsDirectVideo ? 'Yes' : 'No'}</span>
                  <span className="pill">Slideshow: {cap?.supportsPhotoSlideshow ? 'Yes' : 'No'}</span>
                </div>

                <div className="mt-3 rounded-xl border border-slate-100 bg-slate-50/80 p-2.5 text-xs text-slate-600">
                  {hasWarning ? (
                    <p className="flex items-center gap-1.5 text-amber-700"><AlertTriangle className="h-3.5 w-3.5" />{account.health?.message}</p>
                  ) : (
                    <p className="flex items-center gap-1.5 text-emerald-700"><CheckCircle2 className="h-3.5 w-3.5" />Token status healthy</p>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      </section>

      <section className="panel p-4">
        <div className="mb-4 flex items-center gap-2">
          <KeyRound className="h-4 w-4 text-slate-500" />
          <h3 className="text-sm font-semibold text-slate-900">Manual token connect</h3>
        </div>

        <div className="grid gap-3">
          <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-3">
            <p className="mb-2 text-sm font-semibold text-slate-800">Instagram</p>
            <div className="grid gap-2 md:grid-cols-3">
              <input className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm" placeholder="Instagram User ID" value={igUserId} onChange={(e) => setIgUserId(e.target.value)} />
              <input className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm" placeholder="Display Name (optional)" value={igDisplayName} onChange={(e) => setIgDisplayName(e.target.value)} />
              <input className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm" placeholder="Access Token" value={igAccessToken} onChange={(e) => setIgAccessToken(e.target.value)} />
            </div>
            <Button size="sm" className="mt-2 rounded-lg" onClick={() => void connectInstagram()} disabled={loading}>Connect Instagram</Button>
          </div>

          <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-3">
            <p className="mb-2 text-sm font-semibold text-slate-800">YouTube</p>
            <div className="grid gap-2 md:grid-cols-2">
              <input className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm" placeholder="Display Name (optional)" value={ytDisplayName} onChange={(e) => setYtDisplayName(e.target.value)} />
              <input className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm" placeholder="Access Token" value={ytAccessToken} onChange={(e) => setYtAccessToken(e.target.value)} />
            </div>
            <Button size="sm" className="mt-2 rounded-lg" onClick={() => void connectYouTube()} disabled={loading}>Connect YouTube</Button>
          </div>

          <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-3">
            <p className="mb-2 text-sm font-semibold text-slate-800">Facebook</p>
            <div className="grid gap-2 md:grid-cols-3">
              <input className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm" placeholder="Page ID" value={fbPageId} onChange={(e) => setFbPageId(e.target.value)} />
              <input className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm" placeholder="Display Name (optional)" value={fbDisplayName} onChange={(e) => setFbDisplayName(e.target.value)} />
              <input className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm" placeholder="Access Token" value={fbAccessToken} onChange={(e) => setFbAccessToken(e.target.value)} />
            </div>
            <Button size="sm" className="mt-2 rounded-lg" onClick={() => void connectFacebook()} disabled={loading}>Connect Facebook</Button>
          </div>
        </div>
      </section>
    </div>
  );
}
