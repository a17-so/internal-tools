'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { UploadMode, UploadPostType } from '@prisma/client';
import { ClipboardList, Image as ImageIcon, PlayCircle, Trash2, WandSparkles } from 'lucide-react';
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
  videoPath?: string;
  imagePaths?: string[];
  assetLabel: string;
  orderPreview?: string;
};

const TRAY_KEY = 'compose_tray_v2';

function uid() {
  return Math.random().toString(36).slice(2);
}

function getFolderName(file: File, index: number) {
  const withPath = file as File & { webkitRelativePath?: string };
  const rel = withPath.webkitRelativePath || '';
  if (!rel.includes('/')) return `slideshow-${index + 1}`;
  return rel.split('/')[0] || `slideshow-${index + 1}`;
}

function toLines(value: string) {
  return value
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.length > 0);
}

async function runWithConcurrency<T>(
  items: T[],
  worker: (item: T, index: number) => Promise<void>,
  concurrency = 4
) {
  const executing = new Set<Promise<void>>();

  for (let i = 0; i < items.length; i += 1) {
    const p = worker(items[i], i).finally(() => executing.delete(p));
    executing.add(p);
    if (executing.size >= concurrency) {
      await Promise.race(executing);
    }
  }

  await Promise.all(executing);
}

async function stageFiles(files: File[]) {
  const fd = new FormData();
  files.forEach((file) => fd.append('files', file));
  const res = await fetch('/api/uploads/stage', { method: 'POST', body: fd });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.error || 'Failed staging files');
  }
  return data.staged as Array<{ filePath: string; fileName: string }>;
}

export default function ComposeClient({ accounts }: { accounts: ComposeAccount[] }) {
  const [connectedAccountId, setConnectedAccountId] = useState(accounts[0]?.id || '');
  const [mode, setMode] = useState<UploadMode>(UploadMode.draft);
  const [postType, setPostType] = useState<UploadPostType>(UploadPostType.video);
  const [caption, setCaption] = useState('');
  const [video, setVideo] = useState<File | null>(null);
  const [images, setImages] = useState<File[]>([]);

  const [bulkVideoFiles, setBulkVideoFiles] = useState<File[]>([]);
  const [bulkVideoCaptions, setBulkVideoCaptions] = useState('');
  const [bulkSlideFiles, setBulkSlideFiles] = useState<File[]>([]);
  const [bulkSlideCaptions, setBulkSlideCaptions] = useState('');

  const [tray, setTray] = useState<DraftItem[]>([]);
  const [sending, setSending] = useState(false);
  const [staging, setStaging] = useState(false);

  useEffect(() => {
    const raw = localStorage.getItem(TRAY_KEY);
    if (!raw) return;
    try {
      const parsed = JSON.parse(raw) as DraftItem[];
      if (Array.isArray(parsed)) {
        setTray(parsed);
      }
    } catch {
      // ignore invalid local cache
    }
  }, []);

  useEffect(() => {
    localStorage.setItem(TRAY_KEY, JSON.stringify(tray));
  }, [tray]);

  const selected = useMemo(() => accounts.find((a) => a.id === connectedAccountId), [accounts, connectedAccountId]);
  const rawCap = selected?.capabilities?.[0];
  const effectiveCap = useMemo(() => {
    if (!rawCap) return { supportsDraftVideo: true, supportsDirectVideo: false, supportsPhotoSlideshow: true, captionLimit: 2200 };
    const restrictedTikTok =
      selected?.provider === 'tiktok' &&
      !rawCap.supportsDraftVideo &&
      !rawCap.supportsDirectVideo &&
      !rawCap.supportsPhotoSlideshow;

    if (restrictedTikTok) {
      return {
        ...rawCap,
        supportsDraftVideo: true,
        supportsPhotoSlideshow: true,
        supportsDirectVideo: false,
        captionLimit: 2200,
      };
    }

    return rawCap;
  }, [rawCap, selected?.provider]);

  const isScopeLimitedTikTok = useMemo(
    () =>
      selected?.provider === 'tiktok'
      && !rawCap?.supportsDraftVideo
      && !rawCap?.supportsDirectVideo
      && !rawCap?.supportsPhotoSlideshow,
    [rawCap, selected?.provider]
  );

  const modeOptions = useMemo(() => {
    const options: UploadMode[] = [];
    if (effectiveCap.supportsDraftVideo) options.push(UploadMode.draft);
    if (effectiveCap.supportsDirectVideo) options.push(UploadMode.direct);
    return options.length ? options : [UploadMode.draft];
  }, [effectiveCap]);

  const postTypeOptions = useMemo(() => {
    const options: UploadPostType[] = [UploadPostType.video];
    if (effectiveCap.supportsPhotoSlideshow) options.push(UploadPostType.slideshow);
    return options;
  }, [effectiveCap]);

  const accountLabel = (accountId: string) => {
    const account = accounts.find((a) => a.id === accountId);
    if (!account) return accountId;
    const suffix = account.displayName || (account.username ? `@${account.username}` : 'username unavailable (scope-limited)');
    return `${account.provider} · ${suffix}`;
  };

  const onAccountChange = (nextId: string) => {
    setConnectedAccountId(nextId);
  };

  const clearSingleInputs = () => {
    setCaption('');
    setVideo(null);
    setImages([]);
    const vidInput = document.getElementById('compose-video') as HTMLInputElement | null;
    if (vidInput) vidInput.value = '';
    const imageInput = document.getElementById('compose-images') as HTMLInputElement | null;
    if (imageInput) imageInput.value = '';
  };

  const addSingleToTray = async () => {
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

    setStaging(true);
    try {
      if (postType === UploadPostType.video) {
        if (!video) {
          toast.error('Select a video file');
          return;
        }
        const staged = await stageFiles([video]);
        setTray((prev) => [
          ...prev,
          {
            id: uid(),
            connectedAccountId,
            mode,
            postType,
            caption,
            videoPath: staged[0]?.filePath,
            assetLabel: staged[0]?.fileName || video.name,
          },
        ]);
      } else {
        if (images.length < 2 || images.length > 35) {
          toast.error('Slideshows need 2-35 images');
          return;
        }
        const staged = await stageFiles(images);
        setTray((prev) => [
          ...prev,
          {
            id: uid(),
            connectedAccountId,
            mode,
            postType,
            caption,
            imagePaths: staged.map((x) => x.filePath),
            assetLabel: `${images.length} images`,
          },
        ]);
      }

      clearSingleInputs();
      toast.success('Added to batch tray');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to add item');
    } finally {
      setStaging(false);
    }
  };

  const addBulkVideosToTray = async () => {
    if (!bulkVideoFiles.length) {
      toast.error('Choose one or more video files');
      return;
    }

    const lines = toLines(bulkVideoCaptions);
    setStaging(true);
    try {
      const staged = await stageFiles(bulkVideoFiles);
      setTray((prev) => [
        ...prev,
        ...staged.map((item, index) => ({
          id: uid(),
          connectedAccountId,
          mode,
          postType: UploadPostType.video,
          caption: lines[index] || '',
          videoPath: item.filePath,
          assetLabel: item.fileName,
        })),
      ]);
      setBulkVideoFiles([]);
      setBulkVideoCaptions('');
      const bulkInput = document.getElementById('bulk-videos') as HTMLInputElement | null;
      if (bulkInput) bulkInput.value = '';
      toast.success(`Added ${staged.length} videos`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Bulk add failed');
    } finally {
      setStaging(false);
    }
  };

  const addBulkSlideshowsToTray = async () => {
    if (!bulkSlideFiles.length) {
      toast.error('Select slideshow folders first');
      return;
    }

    const grouped = new Map<string, File[]>();
    bulkSlideFiles.forEach((file, index) => {
      const key = getFolderName(file, index);
      const current = grouped.get(key) || [];
      current.push(file);
      grouped.set(key, current);
    });

    const entries = Array.from(grouped.entries()).map(([folder, files]) => ({
      folder,
      files: [...files].sort((a, b) => a.name.localeCompare(b.name)),
    }));

    const validEntries = entries.filter((entry) => entry.files.length >= 2 && entry.files.length <= 35);
    if (!validEntries.length) {
      toast.error('No valid slideshow folders found (need 2-35 images per folder)');
      return;
    }

    const lines = toLines(bulkSlideCaptions);
    setStaging(true);
    try {
      const flatFiles = validEntries.flatMap((entry) => entry.files);
      const stagedFlat = await stageFiles(flatFiles);
      let cursor = 0;

      const created: DraftItem[] = validEntries.map((entry, index) => {
        const slice = stagedFlat.slice(cursor, cursor + entry.files.length);
        cursor += entry.files.length;

        return {
          id: uid(),
          connectedAccountId,
          mode,
          postType: UploadPostType.slideshow,
          caption: lines[index] || '',
          imagePaths: slice.map((x) => x.filePath),
          assetLabel: `${entry.folder} (${entry.files.length} images)`,
          orderPreview: entry.files.map((f) => f.name).slice(0, 5).join(' -> '),
        };
      });

      setTray((prev) => [...prev, ...created]);
      setBulkSlideFiles([]);
      setBulkSlideCaptions('');
      const folderInput = document.getElementById('bulk-slides') as HTMLInputElement | null;
      if (folderInput) folderInput.value = '';
      toast.success(`Added ${created.length} slideshows`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Bulk slideshow add failed');
    } finally {
      setStaging(false);
    }
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

      await runWithConcurrency(tray, async (item) => {
        const res = await fetch('/api/uploads/jobs', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            connectedAccountId: item.connectedAccountId,
            mode: item.mode,
            postType: item.postType,
            caption: item.caption,
            videoPath: item.videoPath,
            imagePaths: item.imagePaths,
            batchId,
            sendNow: false,
          }),
        });
        const data = await res.json();
        if (!res.ok) {
          throw new Error(data.error || 'Failed to enqueue job');
        }
      }, 4);

      await fetch('/api/dispatcher/run', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mode: 'all_queued' }) });
      setTray([]);
      localStorage.removeItem(TRAY_KEY);
      toast.success('Queued. Open Queue to track publish/draft results.');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Batch send failed');
    } finally {
      setSending(false);
    }
  };

  if (accounts.length === 0) {
    return (
      <section className="panel p-6">
        <h3 className="text-lg font-semibold">No Connected Accounts</h3>
        <p className="mt-1 text-sm text-muted-foreground">Connect at least one account before composing posts.</p>
        <Button asChild className="mt-4 rounded-xl">
          <Link href="/accounts">Go to Accounts</Link>
        </Button>
      </section>
    );
  }

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_420px]">
      <div className="space-y-4">
        <section className="panel p-4">
          <div className="mb-3 flex items-center gap-2">
            <WandSparkles className="h-4 w-4 text-indigo-600" />
            <h3 className="text-base font-semibold">Compose</h3>
          </div>

          {isScopeLimitedTikTok ? (
            <div className="mb-3 rounded-lg border border-amber-300 bg-amber-50 p-2.5 text-xs text-amber-800">
              TikTok account is connected with limited scope. Queueing works, but publishing/drafts can fail until `video.upload` / `video.publish` scopes are approved.
            </div>
          ) : null}

          <div className="grid gap-3 lg:grid-cols-2">
            <div className="space-y-2">
              <Label>Account</Label>
              <select className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2" value={connectedAccountId} onChange={(e) => onAccountChange(e.target.value)}>
                {accounts.map((account) => (
                  <option key={account.id} value={account.id}>
                    {account.provider} · {account.displayName || (account.username ? `@${account.username}` : 'username unavailable (scope-limited)')}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-2">
              <Label>Mode</Label>
              <select className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2" value={mode} onChange={(e) => setMode(e.target.value as UploadMode)}>
                {modeOptions.includes(UploadMode.draft) ? <option value={UploadMode.draft}>Draft</option> : null}
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
                <p className="text-xs text-slate-500">{caption.length}/{effectiveCap.captionLimit || 2200}</p>
              </div>
              <textarea
                value={caption}
                onChange={(e) => setCaption(e.target.value)}
                maxLength={effectiveCap.captionLimit || 2200}
                placeholder="Caption"
                className="min-h-[96px] w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm"
              />
            </div>

            {postType === UploadPostType.video ? (
              <div className="space-y-2 md:col-span-2">
                <div className="flex items-center gap-2">
                  <PlayCircle className="h-4 w-4 text-slate-500" />
                  <Label>Video File</Label>
                </div>
                <Input id="compose-video" type="file" accept="video/*" onChange={(e) => setVideo(e.target.files?.[0] || null)} className="rounded-xl" />
              </div>
            ) : (
              <div className="space-y-2 md:col-span-2">
                <div className="flex items-center gap-2">
                  <ImageIcon className="h-4 w-4 text-slate-500" />
                  <Label>Slideshow Images</Label>
                </div>
                <Input id="compose-images" type="file" accept="image/*" multiple onChange={(e) => setImages(Array.from(e.target.files || []))} className="rounded-xl" />
              </div>
            )}

            <div className="md:col-span-2">
              <Button className="rounded-xl" disabled={staging} onClick={() => void addSingleToTray()}>
                {staging ? 'Staging...' : 'Add To Batch Tray'}
              </Button>
            </div>
          </div>
        </section>

        <section className="panel p-4">
          <h3 className="mb-3 text-sm font-semibold">Bulk Videos</h3>
          <div className="space-y-2">
            <Input id="bulk-videos" type="file" accept="video/*" multiple onChange={(e) => setBulkVideoFiles(Array.from(e.target.files || []))} className="rounded-xl" />
            <textarea
              value={bulkVideoCaptions}
              onChange={(e) => setBulkVideoCaptions(e.target.value)}
              placeholder="Paste captions here, one caption per line (line 1 = video 1)"
              className="min-h-[120px] w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm"
            />
            <Button variant="outline" className="rounded-xl" disabled={staging || bulkVideoFiles.length === 0} onClick={() => void addBulkVideosToTray()}>
              Add {bulkVideoFiles.length || ''} Videos To Tray
            </Button>
          </div>
        </section>

        <section className="panel p-4">
          <h3 className="mb-3 text-sm font-semibold">Bulk Slideshows (Folders)</h3>
          <div className="space-y-2">
            <Input
              id="bulk-slides"
              type="file"
              accept="image/*"
              multiple
              className="rounded-xl"
              onChange={(e) => setBulkSlideFiles(Array.from(e.target.files || []))}
              // @ts-expect-error webkitdirectory is non-standard but supported by Chromium browsers.
              webkitdirectory=""
            />
            <textarea
              value={bulkSlideCaptions}
              onChange={(e) => setBulkSlideCaptions(e.target.value)}
              placeholder="Paste captions here, one caption per folder/slideshow"
              className="min-h-[120px] w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm"
            />
            <p className="text-xs text-muted-foreground">Image order inside each slideshow is alphabetical by filename.</p>
            <Button variant="outline" className="rounded-xl" disabled={staging || bulkSlideFiles.length === 0} onClick={() => void addBulkSlideshowsToTray()}>
              Add Slideshows To Tray
            </Button>
          </div>
        </section>
      </div>

      <aside className="space-y-4 xl:sticky xl:top-5 xl:h-[calc(100vh-2.5rem)] xl:overflow-auto">
        <section className="panel p-4">
          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <ClipboardList className="h-4 w-4 text-indigo-600" />
              <h3 className="text-lg font-semibold">Batch Tray</h3>
            </div>
            <span className="pill">{tray.length} posts</span>
          </div>

          <div className="flex gap-2">
            <Button className="flex-1 rounded-xl" onClick={() => void sendAll()} disabled={sending || tray.length === 0}>
              {sending ? 'Sending...' : 'Send All'}
            </Button>
            <Button variant="outline" className="rounded-xl" onClick={() => { setTray([]); localStorage.removeItem(TRAY_KEY); }} disabled={!tray.length || sending}>
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>

          {!tray.length ? <p className="mt-3 text-sm text-slate-500">Tray is empty.</p> : null}
        </section>

        <section className="space-y-2">
          {tray.map((item) => (
            <article key={item.id} className="panel border-slate-200 p-3">
              <div className="mb-1 flex flex-wrap items-center gap-2">
                <span className="pill">{item.postType.toUpperCase()}</span>
                <span className="pill">{item.mode.toUpperCase()}</span>
              </div>
              <p className="text-xs text-slate-500">{accountLabel(item.connectedAccountId)}</p>
              <p className="mt-1 text-xs text-slate-500">{item.assetLabel}</p>
              {item.orderPreview ? <p className="mt-1 text-xs text-muted-foreground">Order: {item.orderPreview}{item.imagePaths && item.imagePaths.length > 5 ? ' ...' : ''}</p> : null}
              <p className="mt-1.5 line-clamp-3 text-sm text-slate-700">{item.caption || '(No caption)'}</p>
              <div className="mt-2 flex items-center justify-end">
                <Button variant="outline" size="sm" className="rounded-lg" onClick={() => setTray((prev) => prev.filter((x) => x.id !== item.id))}>Remove</Button>
              </div>
            </article>
          ))}
        </section>
      </aside>
    </div>
  );
}
