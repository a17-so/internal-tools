'use client';

import { useMemo, useState } from 'react';
import { UploadMode, UploadPostType } from '@prisma/client';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { toast } from 'sonner';

export type ComposeAccount = {
  id: string;
  provider: string;
  displayName: string | null;
  username: string | null;
  capabilities: Array<{
    supportsDraftVideo: boolean;
    supportsDirectVideo: boolean;
    supportsPhotoSlideshow: boolean;
    captionLimit: number;
  }>;
};

type DraftItem = {
  id: string;
  connectedAccountId: string;
  mode: UploadMode;
  postType: UploadPostType;
  caption: string;
  video?: File;
  images?: File[];
};

function uid() {
  return Math.random().toString(36).slice(2);
}

export default function ComposeClient({ accounts }: { accounts: ComposeAccount[] }) {
  const [connectedAccountId, setConnectedAccountId] = useState(accounts[0]?.id || '');
  const [mode, setMode] = useState<UploadMode>(UploadMode.draft);
  const [postType, setPostType] = useState<UploadPostType>(UploadPostType.video);
  const [caption, setCaption] = useState('');
  const [video, setVideo] = useState<File | null>(null);
  const [images, setImages] = useState<File[]>([]);
  const [tray, setTray] = useState<DraftItem[]>([]);
  const [sending, setSending] = useState(false);

  const selected = useMemo(() => accounts.find((a) => a.id === connectedAccountId), [accounts, connectedAccountId]);
  const cap = selected?.capabilities?.[0];

  const addToTray = () => {
    if (!connectedAccountId) {
      toast.error('Pick an account');
      return;
    }

    if (postType === UploadPostType.video && !video) {
      toast.error('Select a video file');
      return;
    }

    if (postType === UploadPostType.slideshow && (images.length < 2 || images.length > 35)) {
      toast.error('Slideshows need 2-35 images');
      return;
    }

    setTray((prev) => [...prev, {
      id: uid(),
      connectedAccountId,
      mode,
      postType,
      caption,
      video: video || undefined,
      images: images.length ? images : undefined,
    }]);

    setCaption('');
    setVideo(null);
    setImages([]);
    const vidInput = document.getElementById('compose-video') as HTMLInputElement | null;
    if (vidInput) vidInput.value = '';
    const imageInput = document.getElementById('compose-images') as HTMLInputElement | null;
    if (imageInput) imageInput.value = '';
    toast.success('Added to batch tray');
  };

  const sendAll = async () => {
    if (!tray.length) {
      toast.error('No queued posts in tray');
      return;
    }

    setSending(true);
    try {
      const batchRes = await fetch('/api/uploads/batches', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: `Web Batch ${new Date().toISOString()}`, jobs: [], sendNow: false }),
      });

      const batchData = await batchRes.json();
      if (!batchRes.ok) {
        throw new Error(batchData.error || 'Failed to create batch');
      }

      const batchId = batchData.batch.id;

      for (const item of tray) {
        const fd = new FormData();
        fd.set('connectedAccountId', item.connectedAccountId);
        fd.set('mode', item.mode);
        fd.set('postType', item.postType);
        fd.set('caption', item.caption);
        fd.set('batchId', batchId);
        fd.set('sendNow', 'false');

        if (item.postType === UploadPostType.video && item.video) {
          fd.set('video', item.video);
        } else if (item.postType === UploadPostType.slideshow && item.images) {
          item.images.forEach((img) => fd.append('images', img));
        }

        const res = await fetch('/api/uploads/jobs', {
          method: 'POST',
          body: fd,
        });

        const data = await res.json();
        if (!res.ok) {
          throw new Error(data.error || 'Failed to enqueue job');
        }
      }

      await fetch('/api/dispatcher/run', { method: 'POST' });
      setTray([]);
      toast.success('Batch submitted and dispatch started');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Batch send failed');
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="grid gap-4 rounded-xl border border-slate-200 bg-white p-4 md:grid-cols-2">
        <div className="space-y-2">
          <Label>Account</Label>
          <select
            className="w-full rounded-md border border-slate-300 bg-white px-3 py-2"
            value={connectedAccountId}
            onChange={(e) => setConnectedAccountId(e.target.value)}
          >
            {accounts.map((account) => (
              <option key={account.id} value={account.id}>
                {account.displayName || account.username || account.id}
              </option>
            ))}
          </select>
        </div>

        <div className="space-y-2">
          <Label>Mode</Label>
          <select className="w-full rounded-md border border-slate-300 bg-white px-3 py-2" value={mode} onChange={(e) => setMode(e.target.value as UploadMode)}>
            <option value={UploadMode.draft}>Draft (preferred)</option>
            {cap?.supportsDirectVideo ? <option value={UploadMode.direct}>Direct</option> : null}
          </select>
        </div>

        <div className="space-y-2">
          <Label>Post Type</Label>
          <select className="w-full rounded-md border border-slate-300 bg-white px-3 py-2" value={postType} onChange={(e) => setPostType(e.target.value as UploadPostType)}>
            <option value={UploadPostType.video}>Video</option>
            {cap?.supportsPhotoSlideshow ? <option value={UploadPostType.slideshow}>Slideshow</option> : null}
          </select>
        </div>

        <div className="space-y-2">
          <Label>Caption</Label>
          <Input value={caption} onChange={(e) => setCaption(e.target.value)} maxLength={cap?.captionLimit || 2200} placeholder="Caption + hashtags" />
          <p className="text-xs text-slate-500">{caption.length}/{cap?.captionLimit || 2200}</p>
        </div>

        {postType === UploadPostType.video ? (
          <div className="space-y-2 md:col-span-2">
            <Label>Video File</Label>
            <Input id="compose-video" type="file" accept="video/mp4,video/webm,video/quicktime" onChange={(e) => setVideo(e.target.files?.[0] || null)} />
          </div>
        ) : (
          <div className="space-y-2 md:col-span-2">
            <Label>Slideshow Images</Label>
            <Input
              id="compose-images"
              type="file"
              accept="image/png,image/jpeg,image/webp"
              multiple
              onChange={(e) => setImages(Array.from(e.target.files || []))}
            />
            <p className="text-xs text-slate-500">Upload in the desired sequence.</p>
          </div>
        )}

        <div className="md:col-span-2">
          <Button onClick={addToTray}>Add To Batch Tray</Button>
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-slate-900">Batch Tray ({tray.length})</h3>
          <Button onClick={sendAll} disabled={sending || tray.length === 0}>
            {sending ? 'Sending...' : 'Send All'}
          </Button>
        </div>

        {!tray.length ? <p className="text-sm text-slate-500">No items added yet.</p> : null}

        <div className="space-y-2">
          {tray.map((item) => (
            <div key={item.id} className="flex items-center justify-between rounded border border-slate-200 px-3 py-2 text-sm">
              <div>
                <p className="font-medium text-slate-900">{item.postType.toUpperCase()} · {item.mode.toUpperCase()}</p>
                <p className="text-slate-600">{item.caption || '(No caption)'}</p>
              </div>
              <Button variant="outline" onClick={() => setTray((prev) => prev.filter((x) => x.id !== item.id))}>Remove</Button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
