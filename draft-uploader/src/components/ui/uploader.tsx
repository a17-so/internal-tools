'use client';

import { useEffect, useMemo, useRef, useState, type InputHTMLAttributes } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { toast } from 'sonner';

type AccountOption = {
  id: string;
  displayName: string;
  openId: string;
};

type UploaderProps = {
  accounts: AccountOption[];
};

type PostType = 'video' | 'slideshow';
type ComposeMode = 'single-video' | 'single-slideshow' | 'bulk-videos' | 'bulk-slideshows';

type TrayItem = {
  id: string;
  stagedUploadId: string;
  tiktokAccountId: string;
  postType: PostType;
  caption: string;
  fileCount: number;
  label: string;
};

type StageResponse = {
  stagedUpload: {
    id: string;
    tiktokAccountId: string;
    postType: PostType;
    fileCount: number;
    files: Array<{ id: string; name: string; order: number }>;
    expiresAt: string;
  };
};

const numericCollator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' });

function sortedByName(files: File[]) {
  return [...files].sort((a, b) => numericCollator.compare(a.name, b.name));
}

function parseCaptionLines(input: string) {
  return input
    .split(/\r?\n/)
    .map((line) => line.trim());
}

function folderNameFromPath(file: File) {
  const path = (file as File & { webkitRelativePath?: string }).webkitRelativePath || '';
  const segments = path.split('/').filter(Boolean);
  if (segments.length < 2) {
    return null;
  }
  return segments[segments.length - 2] || null;
}

function inputClassName() {
  return 'file:text-foreground placeholder:text-muted-foreground selection:bg-primary selection:text-primary-foreground dark:bg-input/30 border-input h-9 w-full min-w-0 rounded-md border bg-transparent px-3 py-1 text-sm shadow-xs transition-[color,box-shadow] outline-none disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50';
}

export default function Uploader({ accounts }: UploaderProps) {
  const [mode, setMode] = useState<ComposeMode>('single-video');
  const [selectedAccountId, setSelectedAccountId] = useState<string>('');
  const [singleCaption, setSingleCaption] = useState('');
  const [bulkCaptions, setBulkCaptions] = useState('');
  const [singleVideoFile, setSingleVideoFile] = useState<File | null>(null);
  const [singleSlideshowFiles, setSingleSlideshowFiles] = useState<File[]>([]);
  const [bulkVideoFiles, setBulkVideoFiles] = useState<File[]>([]);
  const [bulkSlideshowFolderFiles, setBulkSlideshowFolderFiles] = useState<File[]>([]);
  const [tray, setTray] = useState<TrayItem[]>([]);
  const [isStaging, setIsStaging] = useState(false);
  const [isSendingAll, setIsSendingAll] = useState(false);

  const singleVideoInputRef = useRef<HTMLInputElement | null>(null);
  const singleSlideshowInputRef = useRef<HTMLInputElement | null>(null);
  const bulkVideoInputRef = useRef<HTMLInputElement | null>(null);
  const bulkSlideshowInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (!selectedAccountId && accounts.length > 0) {
      setSelectedAccountId(accounts[0].id);
    }
  }, [accounts, selectedAccountId]);

  const selectedAccountLabel = useMemo(() => {
    const account = accounts.find((item) => item.id === selectedAccountId);
    if (!account) {
      return '';
    }
    return `${account.displayName} (${account.openId})`;
  }, [accounts, selectedAccountId]);

  const stageOne = async (postType: PostType, files: File[]) => {
    const formData = new FormData();
    formData.append('action', 'stage');
    formData.append('postType', postType);
    formData.append('tiktokAccountId', selectedAccountId);

    const fieldName = postType === 'video' ? 'video' : 'images';
    files.forEach((file) => formData.append(fieldName, file));

    const response = await fetch('/api/upload', {
      method: 'POST',
      body: formData,
    });

    const payload = (await response.json()) as StageResponse & { error?: string };
    if (!response.ok) {
      throw new Error(payload.error || 'Failed to stage media');
    }

    return payload.stagedUpload;
  };

  const enforceSingleAccountTray = () => {
    if (tray.length === 0) {
      return true;
    }

    const trayAccountId = tray[0].tiktokAccountId;
    if (trayAccountId !== selectedAccountId) {
      toast.error('Tray already has posts for another TikTok account. Send/Clear tray before switching account.');
      return false;
    }

    return true;
  };

  const addToTray = async () => {
    if (!selectedAccountId) {
      toast.error('Please select a TikTok account first');
      return;
    }

    if (!enforceSingleAccountTray()) {
      return;
    }

    setIsStaging(true);

    try {
      if (mode === 'single-video') {
        if (!singleVideoFile) {
          toast.error('Select a video file first');
          return;
        }

        const staged = await stageOne('video', [singleVideoFile]);
        const caption = singleCaption.trim();
        setTray((prev) => [
          ...prev,
          {
            id: staged.id,
            stagedUploadId: staged.id,
            tiktokAccountId: selectedAccountId,
            postType: 'video',
            caption,
            fileCount: 1,
            label: singleVideoFile.name,
          },
        ]);

        setSingleVideoFile(null);
        setSingleCaption('');
        if (singleVideoInputRef.current) {
          singleVideoInputRef.current.value = '';
        }
        toast.success('Video staged and added to batch tray');
        return;
      }

      if (mode === 'single-slideshow') {
        if (singleSlideshowFiles.length < 2 || singleSlideshowFiles.length > 35) {
          toast.error('A slideshow must contain 2 to 35 images');
          return;
        }

        const staged = await stageOne('slideshow', singleSlideshowFiles);
        const caption = singleCaption.trim();

        setTray((prev) => [
          ...prev,
          {
            id: staged.id,
            stagedUploadId: staged.id,
            tiktokAccountId: selectedAccountId,
            postType: 'slideshow',
            caption,
            fileCount: singleSlideshowFiles.length,
            label: `Slideshow (${singleSlideshowFiles.length} images)`,
          },
        ]);

        setSingleSlideshowFiles([]);
        setSingleCaption('');
        if (singleSlideshowInputRef.current) {
          singleSlideshowInputRef.current.value = '';
        }

        toast.success('Slideshow staged and added to batch tray');
        return;
      }

      if (mode === 'bulk-videos') {
        if (bulkVideoFiles.length === 0) {
          toast.error('Select one or more videos first');
          return;
        }

        const lines = parseCaptionLines(bulkCaptions);
        const orderedVideos = [...bulkVideoFiles];
        const newItems: TrayItem[] = [];

        for (let i = 0; i < orderedVideos.length; i += 1) {
          const file = orderedVideos[i];
          const staged = await stageOne('video', [file]);

          newItems.push({
            id: staged.id,
            stagedUploadId: staged.id,
            tiktokAccountId: selectedAccountId,
            postType: 'video',
            caption: lines[i] || '',
            fileCount: 1,
            label: file.name,
          });
        }

        setTray((prev) => [...prev, ...newItems]);
        setBulkVideoFiles([]);
        if (bulkVideoInputRef.current) {
          bulkVideoInputRef.current.value = '';
        }

        toast.success(`${newItems.length} videos staged and added to batch tray`);
        return;
      }

      if (mode === 'bulk-slideshows') {
        if (bulkSlideshowFolderFiles.length === 0) {
          toast.error('Select a slideshow folder first');
          return;
        }

        const grouped = new Map<string, File[]>();
        for (const file of bulkSlideshowFolderFiles) {
          const folder = folderNameFromPath(file);
          if (!folder) {
            continue;
          }

          const current = grouped.get(folder) ?? [];
          current.push(file);
          grouped.set(folder, current);
        }

        const folderEntries = [...grouped.entries()]
          .map(([folder, files]) => ({ folder, files: sortedByName(files) }))
          .sort((a, b) => numericCollator.compare(a.folder, b.folder));

        const validEntries = folderEntries.filter((entry) => entry.files.length >= 2 && entry.files.length <= 35);
        const invalidCount = folderEntries.length - validEntries.length;

        if (validEntries.length === 0) {
          toast.error('No valid slideshow folders found (each needs 2-35 images)');
          return;
        }

        const lines = parseCaptionLines(bulkCaptions);
        const newItems: TrayItem[] = [];

        for (let i = 0; i < validEntries.length; i += 1) {
          const entry = validEntries[i];
          const staged = await stageOne('slideshow', entry.files);

          newItems.push({
            id: staged.id,
            stagedUploadId: staged.id,
            tiktokAccountId: selectedAccountId,
            postType: 'slideshow',
            caption: lines[i] || '',
            fileCount: entry.files.length,
            label: `${entry.folder} (${entry.files.length} images)`,
          });
        }

        setTray((prev) => [...prev, ...newItems]);
        setBulkSlideshowFolderFiles([]);
        if (bulkSlideshowInputRef.current) {
          bulkSlideshowInputRef.current.value = '';
        }

        if (invalidCount > 0) {
          toast.warning(`Added ${newItems.length} slideshow(s). Ignored ${invalidCount} invalid folder(s).`);
        } else {
          toast.success(`${newItems.length} slideshows staged and added to batch tray`);
        }
      }
    } catch (err: unknown) {
      console.error('Staging error:', err);
      const message = err instanceof Error ? err.message : 'Failed to stage files';
      toast.error(message);
    } finally {
      setIsStaging(false);
    }
  };

  const handleSendAll = async () => {
    if (tray.length === 0) {
      toast.error('No items in batch tray');
      return;
    }

    if (!selectedAccountId) {
      toast.error('Please select a TikTok account first');
      return;
    }

    const uniqueAccounts = new Set(tray.map((item) => item.tiktokAccountId));
    if (uniqueAccounts.size > 1 || !uniqueAccounts.has(selectedAccountId)) {
      toast.error('Tray items must all belong to the selected account');
      return;
    }

    setIsSendingAll(true);

    try {
      const response = await fetch('/api/upload', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          action: 'send-all',
          tiktokAccountId: selectedAccountId,
          concurrency: 2,
          items: tray.map((item) => ({
            stagedUploadId: item.stagedUploadId,
            postType: item.postType,
            caption: item.caption,
          })),
        }),
      });

      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || 'Failed to queue uploads');
      }

      const failed = Array.isArray(payload.jobs)
        ? payload.jobs.filter((job: { status?: string }) => job.status === 'failed').length
        : 0;

      if (failed > 0) {
        toast.error(`${failed} upload job(s) failed. Check server logs for details.`);
        return;
      }

      const queuedCount = typeof payload.queuedCount === 'number' ? payload.queuedCount : tray.length;
      toast.success(`${queuedCount} post(s) queued and dispatched successfully`);
      setTray([]);
    } catch (err: unknown) {
      console.error('Send all error:', err);
      const message = err instanceof Error ? err.message : 'Failed to send batch';
      toast.error(message);
    } finally {
      setIsSendingAll(false);
    }
  };

  return (
    <Card className="mx-auto w-full max-w-4xl">
      <CardHeader>
        <CardTitle>TikTok Draft Uploader</CardTitle>
        <CardDescription>
          Stage videos or photo slideshows, review in the batch tray, then queue everything with Send All.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="account-select">TikTok Account</Label>
            <select
              id="account-select"
              className="w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm shadow-sm disabled:cursor-not-allowed disabled:opacity-50 dark:border-zinc-800 dark:bg-zinc-950"
              value={selectedAccountId}
              onChange={(e) => setSelectedAccountId(e.target.value)}
              disabled={isStaging || isSendingAll || accounts.length === 0}
            >
              {accounts.length === 0 ? (
                <option value="">No linked accounts</option>
              ) : (
                accounts.map((account) => (
                  <option key={account.id} value={account.id}>
                    {account.displayName} ({account.openId})
                  </option>
                ))
              )}
            </select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="compose-mode">Compose Mode</Label>
            <select
              id="compose-mode"
              className="w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm shadow-sm disabled:cursor-not-allowed disabled:opacity-50 dark:border-zinc-800 dark:bg-zinc-950"
              value={mode}
              onChange={(e) => setMode(e.target.value as ComposeMode)}
              disabled={isStaging || isSendingAll}
            >
              <option value="single-video">Single Video</option>
              <option value="single-slideshow">Single Slideshow (2-35 images)</option>
              <option value="bulk-videos">Bulk Videos + Caption Lines</option>
              <option value="bulk-slideshows">Bulk Slideshows by Folder</option>
            </select>
          </div>
        </div>

        {(mode === 'single-video' || mode === 'single-slideshow') ? (
          <div className="space-y-2">
            <Label htmlFor="single-caption">Caption</Label>
            <Input
              id="single-caption"
              placeholder="Awesome post! #fyp"
              value={singleCaption}
              onChange={(e) => setSingleCaption(e.target.value)}
              disabled={isStaging || isSendingAll}
            />
          </div>
        ) : (
          <div className="space-y-2">
            <Label htmlFor="bulk-captions">Captions (one line per post, by position)</Label>
            <textarea
              id="bulk-captions"
              className="w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm shadow-sm disabled:cursor-not-allowed disabled:opacity-50 dark:border-zinc-800 dark:bg-zinc-950"
              rows={6}
              placeholder={'Caption for item 1\nCaption for item 2\nCaption for item 3'}
              value={bulkCaptions}
              onChange={(e) => setBulkCaptions(e.target.value)}
              disabled={isStaging || isSendingAll}
            />
          </div>
        )}

        {mode === 'single-video' ? (
          <div className="space-y-2">
            <Label htmlFor="single-video">Select Video</Label>
            <Input
              id="single-video"
              ref={singleVideoInputRef}
              type="file"
              accept="video/mp4,video/webm"
              onChange={(e) => setSingleVideoFile(e.target.files?.[0] ?? null)}
              disabled={isStaging || isSendingAll}
            />
          </div>
        ) : null}

        {mode === 'single-slideshow' ? (
          <div className="space-y-2">
            <Label htmlFor="single-slideshow">Select Images (2-35)</Label>
            <Input
              id="single-slideshow"
              ref={singleSlideshowInputRef}
              type="file"
              accept="image/*"
              multiple
              onChange={(e) => setSingleSlideshowFiles(e.target.files ? Array.from(e.target.files) : [])}
              disabled={isStaging || isSendingAll}
            />
            <p className="text-xs text-zinc-500">Selected: {singleSlideshowFiles.length} images</p>
          </div>
        ) : null}

        {mode === 'bulk-videos' ? (
          <div className="space-y-2">
            <Label htmlFor="bulk-videos">Select Videos</Label>
            <Input
              id="bulk-videos"
              ref={bulkVideoInputRef}
              type="file"
              accept="video/mp4,video/webm"
              multiple
              onChange={(e) => setBulkVideoFiles(e.target.files ? Array.from(e.target.files) : [])}
              disabled={isStaging || isSendingAll}
            />
            <p className="text-xs text-zinc-500">Selected: {bulkVideoFiles.length} videos</p>
          </div>
        ) : null}

        {mode === 'bulk-slideshows' ? (
          <div className="space-y-2">
            <Label htmlFor="bulk-slideshows">Select Parent Folder (subfolders = slideshows)</Label>
            <input
              id="bulk-slideshows"
              ref={bulkSlideshowInputRef}
              type="file"
              className={inputClassName()}
              multiple
              onChange={(e) => setBulkSlideshowFolderFiles(e.target.files ? Array.from(e.target.files) : [])}
              disabled={isStaging || isSendingAll}
              {...({ webkitdirectory: 'true', directory: 'true' } as unknown as InputHTMLAttributes<HTMLInputElement>)}
            />
            <p className="text-xs text-zinc-500">Files detected: {bulkSlideshowFolderFiles.length}</p>
          </div>
        ) : null}

        <div className="flex flex-wrap gap-2">
          <Button
            onClick={addToTray}
            disabled={isStaging || isSendingAll || !selectedAccountId || accounts.length === 0}
          >
            {isStaging ? 'Staging...' : 'Stage + Add To Batch Tray'}
          </Button>
          <Button
            variant="outline"
            onClick={() => setTray([])}
            disabled={isStaging || isSendingAll || tray.length === 0}
          >
            Clear Tray
          </Button>
        </div>

        <div className="space-y-2 rounded-md border p-3">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium">Batch Tray</p>
            <p className="text-xs text-zinc-500">{tray.length} post(s) queued</p>
          </div>
          {tray.length === 0 ? (
            <p className="text-sm text-zinc-500">No pending posts yet.</p>
          ) : (
            <div className="space-y-2">
              {tray.map((item, index) => (
                <div key={`${item.id}-${index}`} className="flex items-start justify-between rounded-md border border-zinc-200 p-2 text-sm dark:border-zinc-800">
                  <div>
                    <p className="font-medium">{index + 1}. {item.postType === 'video' ? 'Video' : 'Slideshow'}: {item.label}</p>
                    <p className="text-xs text-zinc-500">Caption: {item.caption || '(empty)'}</p>
                  </div>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => setTray((prev) => prev.filter((entry) => entry.id !== item.id))}
                    disabled={isStaging || isSendingAll}
                  >
                    Remove
                  </Button>
                </div>
              ))}
            </div>
          )}
        </div>
      </CardContent>
      <CardFooter className="flex flex-wrap gap-2">
        <Button
          className="w-full md:w-auto"
          onClick={handleSendAll}
          disabled={tray.length === 0 || isSendingAll || isStaging || !selectedAccountId}
        >
          {isSendingAll ? `Queueing ${tray.length} Post(s)...` : `Send All (${tray.length})`}
        </Button>
        {selectedAccountLabel ? <p className="text-xs text-zinc-500">Target account: {selectedAccountLabel}</p> : null}
      </CardFooter>
    </Card>
  );
}
