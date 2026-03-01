'use client';

import { useMemo, useState } from 'react';
import { UploadMode, UploadPostType } from '@prisma/client';
import { DateTime } from 'luxon';
import { CalendarClock, Captions, ClipboardList, Image as ImageIcon, PlayCircle, Trash2, WandSparkles } from 'lucide-react';
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
  scheduleAt?: string;
  scheduleTz?: string;
  video?: File;
  images?: File[];
};

const scheduleTimezones = ['local', 'UTC', 'America/Los_Angeles', 'America/New_York', 'Europe/London'];

function uid() {
  return Math.random().toString(36).slice(2);
}

function reorder<T>(arr: T[], from: number, to: number) {
  const next = [...arr];
  const [item] = next.splice(from, 1);
  next.splice(to, 0, item);
  return next;
}

export default function ComposeClient({ accounts }: { accounts: ComposeAccount[] }) {
  const [connectedAccountId, setConnectedAccountId] = useState(accounts[0]?.id || '');
  const [mode, setMode] = useState<UploadMode>(UploadMode.draft);
  const [postType, setPostType] = useState<UploadPostType>(UploadPostType.video);
  const [caption, setCaption] = useState('');
  const [scheduleAt, setScheduleAt] = useState('');
  const [scheduleTz, setScheduleTz] = useState('local');
  const [video, setVideo] = useState<File | null>(null);
  const [images, setImages] = useState<File[]>([]);
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const [tray, setTray] = useState<DraftItem[]>([]);
  const [sending, setSending] = useState(false);

  const [prependText, setPrependText] = useState('');
  const [appendText, setAppendText] = useState('');
  const [findText, setFindText] = useState('');
  const [replaceText, setReplaceText] = useState('');

  const selected = useMemo(() => accounts.find((a) => a.id === connectedAccountId), [accounts, connectedAccountId]);
  const cap = selected?.capabilities?.[0];

  const modeOptions = useMemo(() => {
    const options: UploadMode[] = [];
    if (cap?.supportsDraftVideo) options.push(UploadMode.draft);
    if (cap?.supportsDirectVideo) options.push(UploadMode.direct);
    return options.length ? options : [UploadMode.draft];
  }, [cap]);

  const postTypeOptions = useMemo(() => {
    const options: UploadPostType[] = [UploadPostType.video];
    if (cap?.supportsPhotoSlideshow) options.push(UploadPostType.slideshow);
    return options;
  }, [cap]);

  const accountLabel = (accountId: string) => {
    const account = accounts.find((a) => a.id === accountId);
    if (!account) return accountId;
    return `${account.provider} · ${account.displayName || account.username || account.id}`;
  };

  const totalAssets = useMemo(
    () => tray.reduce((acc, item) => acc + (item.postType === UploadPostType.video ? 1 : item.images?.length || 0), 0),
    [tray]
  );

  const onAccountChange = (nextId: string) => {
    setConnectedAccountId(nextId);
    const next = accounts.find((a) => a.id === nextId);
    const nextCap = next?.capabilities?.[0];

    const nextModeOptions: UploadMode[] = [];
    if (nextCap?.supportsDraftVideo) nextModeOptions.push(UploadMode.draft);
    if (nextCap?.supportsDirectVideo) nextModeOptions.push(UploadMode.direct);
    if (!nextModeOptions.includes(mode)) {
      setMode(nextModeOptions[0] || UploadMode.draft);
    }

    if (!nextCap?.supportsPhotoSlideshow && postType === UploadPostType.slideshow) {
      setPostType(UploadPostType.video);
      setImages([]);
    }
  };

  const onSelectImages = (files: File[]) => {
    setImages(files);
    setDragIndex(null);
  };

  const clearInputs = () => {
    setCaption('');
    setScheduleAt('');
    setScheduleTz('local');
    setVideo(null);
    setImages([]);
    setDragIndex(null);

    const vidInput = document.getElementById('compose-video') as HTMLInputElement | null;
    if (vidInput) vidInput.value = '';
    const imageInput = document.getElementById('compose-images') as HTMLInputElement | null;
    if (imageInput) imageInput.value = '';
  };

  const addToTray = () => {
    if (!connectedAccountId) {
      toast.error('Pick an account');
      return;
    }

    if (!modeOptions.includes(mode)) {
      toast.error('Selected mode is not supported by this account');
      return;
    }

    if (!postTypeOptions.includes(postType)) {
      toast.error('Selected post type is not supported by this account');
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

    let scheduleAtIso: string | undefined;
    if (scheduleAt) {
      const dt = scheduleTz === 'local'
        ? DateTime.fromISO(scheduleAt)
        : DateTime.fromISO(scheduleAt, { zone: scheduleTz });
      if (!dt.isValid) {
        toast.error('Invalid schedule datetime');
        return;
      }
      scheduleAtIso = dt.toUTC().toISO() || undefined;
    }

    setTray((prev) => [
      ...prev,
      {
        id: uid(),
        connectedAccountId,
        mode,
        postType,
        caption,
        scheduleAt: scheduleAtIso,
        scheduleTz,
        video: video || undefined,
        images: images.length ? images : undefined,
      },
    ]);

    clearInputs();
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
        if (item.scheduleAt) fd.set('scheduleAt', item.scheduleAt);
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
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_420px]">
      <div className="space-y-4">
        <section className="panel p-4">
          <div className="mb-3 flex items-center gap-2">
            <WandSparkles className="h-4 w-4 text-indigo-600" />
            <h3 className="text-base font-semibold text-slate-900">Compose Post</h3>
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            <div className="space-y-2">
              <Label>Account</Label>
              <select className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2" value={connectedAccountId} onChange={(e) => onAccountChange(e.target.value)}>
                {accounts.map((account) => (
                  <option key={account.id} value={account.id}>
                    {account.provider} · {account.displayName || account.username || account.id}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-2">
              <Label>Mode</Label>
              <select className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2" value={mode} onChange={(e) => setMode(e.target.value as UploadMode)}>
                {modeOptions.includes(UploadMode.draft) ? <option value={UploadMode.draft}>Draft (preferred)</option> : null}
                {modeOptions.includes(UploadMode.direct) ? <option value={UploadMode.direct}>Direct</option> : null}
              </select>
            </div>

            <div className="space-y-2">
              <Label>Post Type</Label>
              <select className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2" value={postType} onChange={(e) => setPostType(e.target.value as UploadPostType)}>
                <option value={UploadPostType.video}>Video</option>
                {postTypeOptions.includes(UploadPostType.slideshow) ? <option value={UploadPostType.slideshow}>Slideshow</option> : null}
              </select>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label>Caption</Label>
                <p className="text-xs text-slate-500">{caption.length}/{cap?.captionLimit || 2200}</p>
              </div>
              <textarea
                value={caption}
                onChange={(e) => setCaption(e.target.value)}
                maxLength={cap?.captionLimit || 2200}
                placeholder="Caption + hashtags"
                className="min-h-[96px] w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm"
              />
            </div>

            <div className="space-y-2 md:col-span-2">
              <div className="flex items-center gap-2">
                <CalendarClock className="h-4 w-4 text-slate-500" />
                <Label>Schedule (optional)</Label>
              </div>
              <div className="grid gap-2 md:grid-cols-2">
                <Input type="datetime-local" value={scheduleAt} onChange={(e) => setScheduleAt(e.target.value)} className="rounded-xl" />
                <select className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm" value={scheduleTz} onChange={(e) => setScheduleTz(e.target.value)}>
                  {scheduleTimezones.map((tz) => <option key={tz} value={tz}>{tz}</option>)}
                </select>
              </div>
            </div>

            {postType === UploadPostType.video ? (
              <div className="space-y-2 md:col-span-2">
                <div className="flex items-center gap-2">
                  <PlayCircle className="h-4 w-4 text-slate-500" />
                  <Label>Video File</Label>
                </div>
                <Input id="compose-video" type="file" accept="video/mp4,video/webm,video/quicktime" onChange={(e) => setVideo(e.target.files?.[0] || null)} className="rounded-xl" />
              </div>
            ) : (
              <div className="space-y-3 md:col-span-2">
                <div className="flex items-center gap-2">
                  <ImageIcon className="h-4 w-4 text-slate-500" />
                  <Label>Slideshow Images</Label>
                </div>
                <Input id="compose-images" type="file" accept="image/png,image/jpeg,image/webp" multiple onChange={(e) => onSelectImages(Array.from(e.target.files || []))} className="rounded-xl" />
                <p className="text-xs text-slate-500">Drag rows to reorder sequence or use Up/Down (2-35 images).</p>
                <div className="space-y-2">
                  {images.map((img, idx) => (
                    <div
                      key={`${img.name}-${idx}`}
                      className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm"
                      draggable
                      onDragStart={() => setDragIndex(idx)}
                      onDragOver={(e) => e.preventDefault()}
                      onDrop={() => {
                        if (dragIndex === null || dragIndex === idx) return;
                        setImages((prev) => reorder(prev, dragIndex, idx));
                        setDragIndex(null);
                      }}
                    >
                      <span className="truncate">{idx + 1}. {img.name}</span>
                      <div className="space-x-2">
                        <Button variant="outline" size="sm" onClick={() => setImages((prev) => idx > 0 ? reorder(prev, idx, idx - 1) : prev)}>Up</Button>
                        <Button variant="outline" size="sm" onClick={() => setImages((prev) => idx < prev.length - 1 ? reorder(prev, idx, idx + 1) : prev)}>Down</Button>
                        <Button variant="outline" size="sm" onClick={() => setImages((prev) => prev.filter((_, i) => i !== idx))}>Remove</Button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="md:col-span-2 flex items-center gap-2">
              <Button className="rounded-xl" onClick={addToTray}>Add To Batch Tray</Button>
              <Button variant="outline" className="rounded-xl" onClick={clearInputs}>Clear Form</Button>
            </div>
          </div>
        </section>

        <section className="panel p-4">
          <div className="mb-3 flex items-center gap-2">
            <Captions className="h-4 w-4 text-slate-500" />
            <h3 className="text-sm font-semibold text-slate-900">Bulk Caption Tools</h3>
          </div>
          <div className="grid gap-2 md:grid-cols-4">
            <Input placeholder="Prepend text" value={prependText} onChange={(e) => setPrependText(e.target.value)} className="rounded-xl" />
            <Input placeholder="Append text" value={appendText} onChange={(e) => setAppendText(e.target.value)} className="rounded-xl" />
            <Input placeholder="Find" value={findText} onChange={(e) => setFindText(e.target.value)} className="rounded-xl" />
            <Input placeholder="Replace" value={replaceText} onChange={(e) => setReplaceText(e.target.value)} className="rounded-xl" />
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button variant="outline" className="rounded-xl" onClick={() => setTray((prev) => prev.map((item) => ({ ...item, caption: `${prependText}${item.caption}` })))} disabled={!prependText || !tray.length}>Apply Prepend</Button>
            <Button variant="outline" className="rounded-xl" onClick={() => setTray((prev) => prev.map((item) => ({ ...item, caption: `${item.caption}${appendText}` })))} disabled={!appendText || !tray.length}>Apply Append</Button>
            <Button
              variant="outline"
              className="rounded-xl"
              onClick={() => {
                if (!findText) return;
                setTray((prev) => prev.map((item) => ({ ...item, caption: item.caption.split(findText).join(replaceText) })));
              }}
              disabled={!findText || !tray.length}
            >
              Apply Find/Replace
            </Button>
          </div>
        </section>
      </div>

      <aside className="space-y-4 xl:sticky xl:top-5 xl:h-[calc(100vh-2.5rem)] xl:overflow-auto">
        <section className="panel p-4">
          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <ClipboardList className="h-4 w-4 text-indigo-600" />
              <h3 className="text-lg font-semibold text-slate-900">Batch Tray</h3>
            </div>
            <span className="pill">{tray.length} posts</span>
          </div>

          <div className="mb-3 grid grid-cols-2 gap-2 text-sm">
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-2">
              <p className="text-xs uppercase tracking-[0.08em] text-slate-500">Posts</p>
              <p className="text-lg font-semibold text-slate-900">{tray.length}</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-2">
              <p className="text-xs uppercase tracking-[0.08em] text-slate-500">Assets</p>
              <p className="text-lg font-semibold text-slate-900">{totalAssets}</p>
            </div>
          </div>

          <div className="flex gap-2">
            <Button className="flex-1 rounded-xl" onClick={sendAll} disabled={sending || tray.length === 0}>
              {sending ? 'Sending...' : 'Send All'}
            </Button>
            <Button variant="outline" className="rounded-xl" onClick={() => setTray([])} disabled={!tray.length || sending}>
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>

          {!tray.length ? <p className="mt-3 text-sm text-slate-500">No items added yet.</p> : null}
        </section>

        <section className="space-y-2">
          {tray.map((item) => (
            <article key={item.id} className="panel border-slate-200 p-3">
              <div className="mb-1 flex flex-wrap items-center gap-2">
                <span className="pill">{item.postType.toUpperCase()}</span>
                <span className="pill">{item.mode.toUpperCase()}</span>
              </div>
              <p className="text-xs text-slate-500">{accountLabel(item.connectedAccountId)}</p>
              {item.scheduleAt ? (
                <p className="mt-1 text-xs text-amber-700">
                  Scheduled: {DateTime.fromISO(item.scheduleAt).setZone(item.scheduleTz === 'local' ? DateTime.local().zoneName : item.scheduleTz || 'local').toLocaleString(DateTime.DATETIME_MED)}
                </p>
              ) : null}
              <p className="mt-1.5 line-clamp-3 text-sm text-slate-700">{item.caption || '(No caption)'}</p>
              <div className="mt-2 flex items-center justify-between">
                <p className="text-xs text-slate-500">{item.postType === UploadPostType.video ? item.video?.name : `${item.images?.length || 0} images`}</p>
                <Button variant="outline" size="sm" className="rounded-lg" onClick={() => setTray((prev) => prev.filter((x) => x.id !== item.id))}>Remove</Button>
              </div>
            </article>
          ))}
        </section>
      </aside>
    </div>
  );
}
