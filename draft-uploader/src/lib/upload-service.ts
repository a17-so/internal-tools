import crypto from 'crypto';
import fs from 'fs';
import os from 'os';
import path from 'path';
import { spawn } from 'child_process';
import {
  getStore,
  updateStore,
  type StagedMediaFileRecord,
  type StagedUploadRecord,
  type TikTokAccountRecord,
  type UploadBatchRecord,
  type UploadJobRecord,
  type UploadPostType,
  type UploadBatchStatus,
} from '@/lib/datastore';

const STAGING_TTL_MS = 24 * 60 * 60 * 1000;
const DEFAULT_DISPATCH_CONCURRENCY = 2;

const PHOTO_INIT_ENDPOINTS = [
  'https://open.tiktokapis.com/v2/post/publish/inbox/photo/init/',
  'https://open.tiktokapis.com/v2/post/publish/content/init/',
];

function nowIso() {
  return new Date().toISOString();
}

function ensureDir(dir: string) {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
}

function safeName(input: string) {
  return input.replace(/[^a-zA-Z0-9._-]/g, '_');
}

function stagingRoot() {
  const dir = path.join(process.cwd(), 'data', 'staged-media');
  ensureDir(dir);
  return dir;
}

function uniquePath(prefix: string, originalName: string) {
  const filename = `${prefix}_${safeName(originalName)}`;
  return path.join(stagingRoot(), filename);
}

function parseTikTokError(payload: unknown) {
  if (!payload || typeof payload !== 'object') {
    return undefined;
  }

  const candidate = payload as Record<string, unknown>;
  const err = candidate.error as Record<string, unknown> | undefined;
  if (!err) {
    return undefined;
  }

  const code = typeof err.code === 'string' ? err.code : undefined;
  const message = typeof err.message === 'string' ? err.message : undefined;
  return { code, message };
}

function isTikTokOk(payload: unknown, responseOk: boolean) {
  if (!responseOk) {
    return false;
  }
  const err = parseTikTokError(payload);
  if (!err?.code) {
    return true;
  }
  return err.code === 'ok';
}

function extractPublishId(payload: unknown) {
  if (!payload || typeof payload !== 'object') {
    return undefined;
  }

  const data = (payload as Record<string, unknown>).data;
  if (!data || typeof data !== 'object') {
    return undefined;
  }

  const record = data as Record<string, unknown>;
  const candidates = ['publish_id', 'publishId', 'task_id', 'taskId', 'post_id', 'postId'];
  for (const key of candidates) {
    if (typeof record[key] === 'string') {
      return record[key] as string;
    }
  }

  return undefined;
}

function extractUploadUrls(payload: unknown): string[] {
  if (!payload || typeof payload !== 'object') {
    return [];
  }
  const data = (payload as Record<string, unknown>).data;
  if (!data || typeof data !== 'object') {
    return [];
  }

  const sourceInfo = (data as Record<string, unknown>).source_info;
  const container = sourceInfo && typeof sourceInfo === 'object' ? sourceInfo : data;
  const record = container as Record<string, unknown>;
  const fields = ['upload_urls', 'upload_url_list', 'upload_url'];

  for (const field of fields) {
    const value = record[field];
    if (Array.isArray(value)) {
      return value.filter((item): item is string => typeof item === 'string');
    }
    if (typeof value === 'string') {
      return [value];
    }
  }

  return [];
}

function byOrder(files: StagedMediaFileRecord[]) {
  return [...files].sort((a, b) => a.order - b.order);
}

async function putBinary(url: string, filePath: string, mimeType: string) {
  const buffer = await fs.promises.readFile(filePath);
  const response = await fetch(url, {
    method: 'PUT',
    headers: {
      'Content-Type': mimeType,
      'Content-Length': buffer.length.toString(),
    },
    body: buffer,
  });

  if (!response.ok) {
    const errText = await response.text();
    throw new Error(`Binary upload failed (${response.status}): ${errText.slice(0, 400)}`);
  }
}

async function uploadVideoFile(accessToken: string, filePath: string, mimeType: string, title?: string) {
  const stat = await fs.promises.stat(filePath);
  const fileSize = stat.size;

  const initResponse = await fetch('https://open.tiktokapis.com/v2/post/publish/inbox/video/init/', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${accessToken}`,
      'Content-Type': 'application/json; charset=UTF-8',
    },
    body: JSON.stringify({
      source_info: {
        source: 'FILE_UPLOAD',
        video_size: fileSize,
        chunk_size: fileSize,
        total_chunk_count: 1,
      },
      ...(title ? { post_info: { title } } : {}),
    }),
  });

  const initData = await initResponse.json();
  if (!isTikTokOk(initData, initResponse.ok)) {
    const err = parseTikTokError(initData);
    throw new Error(err?.message || 'TikTok video initialization failed');
  }

  const uploadUrl = (initData as Record<string, unknown>)?.data &&
    typeof (initData as Record<string, unknown>).data === 'object'
    ? ((initData as Record<string, unknown>).data as Record<string, unknown>).upload_url as string | undefined
    : undefined;

  if (!uploadUrl) {
    throw new Error('TikTok did not return a video upload URL');
  }

  const videoBuffer = await fs.promises.readFile(filePath);
  const uploadResponse = await fetch(uploadUrl, {
    method: 'PUT',
    headers: {
      'Content-Range': `bytes 0-${fileSize - 1}/${fileSize}`,
      'Content-Type': mimeType || 'video/mp4',
      'Content-Length': fileSize.toString(),
    },
    body: videoBuffer,
  });

  if (!uploadResponse.ok) {
    const uploadErrorText = await uploadResponse.text();
    throw new Error(`TikTok video upload failed (${uploadResponse.status}): ${uploadErrorText.slice(0, 400)}`);
  }

  return {
    publishId: extractPublishId(initData),
    raw: initData,
  };
}

async function tryInitAndUploadPhotos(accessToken: string, imageFiles: StagedMediaFileRecord[], title?: string) {
  const ordered = byOrder(imageFiles);

  for (const endpoint of PHOTO_INIT_ENDPOINTS) {
    try {
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${accessToken}`,
          'Content-Type': 'application/json; charset=UTF-8',
        },
        body: JSON.stringify({
          source_info: {
            source: 'FILE_UPLOAD',
            photo_count: ordered.length,
            total_photo_count: ordered.length,
          },
          media_info: {
            media_type: 'PHOTO',
            photo_count: ordered.length,
          },
          ...(title ? { post_info: { title } } : {}),
        }),
      });

      const payload = await response.json();
      if (!isTikTokOk(payload, response.ok)) {
        continue;
      }

      const uploadUrls = extractUploadUrls(payload);
      if (uploadUrls.length < ordered.length) {
        continue;
      }

      for (let i = 0; i < ordered.length; i += 1) {
        const item = ordered[i];
        const uploadUrl = uploadUrls[i];
        const mimeType = item.mimeType || 'image/jpeg';
        await putBinary(uploadUrl, item.stagedPath, mimeType);
      }

      return {
        publishId: extractPublishId(payload),
        raw: payload,
      };
    } catch {
      // Try the next endpoint.
    }
  }

  return null;
}

function runFfmpeg(args: string[]) {
  return new Promise<void>((resolve, reject) => {
    const proc = spawn('ffmpeg', args, { stdio: 'pipe' });
    let stderr = '';

    proc.stderr.on('data', (chunk) => {
      stderr += chunk.toString();
    });

    proc.on('error', (err) => {
      reject(new Error(`Unable to start ffmpeg: ${err.message}`));
    });

    proc.on('close', (code) => {
      if (code === 0) {
        resolve();
      } else {
        reject(new Error(`ffmpeg failed (${code}): ${stderr.slice(0, 1200)}`));
      }
    });
  });
}

function escapeConcatPath(filePath: string) {
  return filePath.replace(/'/g, "'\\''");
}

async function buildSlideshowVideo(imageFiles: StagedMediaFileRecord[]) {
  const sorted = byOrder(imageFiles);
  const tmpDir = await fs.promises.mkdtemp(path.join(os.tmpdir(), 'du-slideshow-'));
  const listPath = path.join(tmpDir, 'input.txt');
  const outputPath = path.join(tmpDir, 'slideshow.mp4');
  const perImageDuration = 1.2;

  const lines: string[] = [];
  sorted.forEach((file, index) => {
    lines.push(`file '${escapeConcatPath(file.stagedPath)}'`);
    if (index !== sorted.length - 1) {
      lines.push(`duration ${perImageDuration}`);
    }
  });

  await fs.promises.writeFile(listPath, lines.join('\n'), 'utf8');

  await runFfmpeg([
    '-y',
    '-f', 'concat',
    '-safe', '0',
    '-i', listPath,
    '-vf', 'scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,format=yuv420p',
    '-r', '30',
    '-c:v', 'libx264',
    '-pix_fmt', 'yuv420p',
    '-movflags', '+faststart',
    outputPath,
  ]);

  return {
    outputPath,
    cleanup: async () => {
      await fs.promises.rm(tmpDir, { recursive: true, force: true });
    },
  };
}

async function uploadSlideshow(
  accessToken: string,
  imageFiles: StagedMediaFileRecord[],
  title?: string,
) {
  const nativeResult = await tryInitAndUploadPhotos(accessToken, imageFiles, title);
  if (nativeResult) {
    return {
      publishId: nativeResult.publishId,
      usedVideoFallback: false,
    };
  }

  const rendered = await buildSlideshowVideo(imageFiles);
  try {
    const videoResult = await uploadVideoFile(accessToken, rendered.outputPath, 'video/mp4', title);
    return {
      publishId: videoResult.publishId,
      usedVideoFallback: true,
    };
  } finally {
    await rendered.cleanup();
  }
}

function recalcBatch(batch: UploadBatchRecord) {
  const store = getStore();
  const jobs = store.uploadJobs.filter((item) => item.batchId === batch.id);
  const queuedJobs = jobs.filter((item) => item.status === 'queued').length;
  const completedJobs = jobs.filter((item) => item.status === 'completed').length;
  const failedJobs = jobs.filter((item) => item.status === 'failed').length;

  let status: UploadBatchStatus = 'processing';
  if (queuedJobs === jobs.length) {
    status = 'queued';
  }
  if (queuedJobs === 0 && completedJobs + failedJobs === jobs.length) {
    status = failedJobs > 0 ? 'failed' : 'completed';
  }

  updateStore((next) => {
    const idx = next.uploadBatches.findIndex((item) => item.id === batch.id);
    if (idx >= 0) {
      next.uploadBatches[idx] = {
        ...next.uploadBatches[idx],
        updatedAt: nowIso(),
        queuedJobs,
        completedJobs,
        failedJobs,
        totalJobs: jobs.length,
        status,
      };
    }
  });
}

function markJob(jobId: string, patch: Partial<UploadJobRecord>) {
  updateStore((store) => {
    const idx = store.uploadJobs.findIndex((item) => item.id === jobId);
    if (idx < 0) {
      return;
    }
    store.uploadJobs[idx] = {
      ...store.uploadJobs[idx],
      ...patch,
      updatedAt: nowIso(),
    };
  });
}

function claimNextQueuedJob(batchId: string): UploadJobRecord | null {
  let claimed: UploadJobRecord | null = null;
  updateStore((store) => {
    const idx = store.uploadJobs.findIndex((item) => item.batchId === batchId && item.status === 'queued');
    if (idx < 0) {
      return;
    }

    const next = store.uploadJobs[idx];
    const claimedAt = nowIso();
    const updated: UploadJobRecord = {
      ...next,
      status: 'processing',
      startedAt: claimedAt,
      updatedAt: claimedAt,
    };
    store.uploadJobs[idx] = updated;
    claimed = updated;
  });

  return claimed;
}

function getAccountAndStaging(job: UploadJobRecord): { account?: TikTokAccountRecord; staged?: StagedUploadRecord } {
  const store = getStore();
  return {
    account: store.tiktokAccounts.find((item) => item.id === job.tiktokAccountId),
    staged: store.stagedUploads.find((item) => item.id === job.stagedUploadId),
  };
}

async function processJob(job: UploadJobRecord) {
  const { account, staged } = getAccountAndStaging(job);
  if (!account) {
    throw new Error('TikTok account not found for job');
  }
  if (!staged) {
    throw new Error('Staged files not found for job');
  }

  if (job.postType === 'video') {
    const video = staged.files[0];
    if (!video) {
      throw new Error('Missing staged video file');
    }

    const result = await uploadVideoFile(account.accessToken, video.stagedPath, video.mimeType, job.caption);
    return {
      publishId: result.publishId,
      usedVideoFallback: false,
    };
  }

  if (staged.files.length < 2 || staged.files.length > 35) {
    throw new Error('Slideshow must contain between 2 and 35 images');
  }

  return uploadSlideshow(account.accessToken, staged.files, job.caption);
}

export async function stageUpload(args: {
  userId: string;
  tiktokAccountId: string;
  postType: UploadPostType;
  files: File[];
}) {
  const now = Date.now();
  const createdAt = new Date(now).toISOString();
  const expiresAt = new Date(now + STAGING_TTL_MS).toISOString();
  const stagedUploadId = crypto.randomUUID();

  const stagedFiles: StagedMediaFileRecord[] = [];

  for (let i = 0; i < args.files.length; i += 1) {
    const file = args.files[i];
    const fileId = crypto.randomUUID();
    const filePath = uniquePath(`${stagedUploadId}_${i}`, file.name);
    const buffer = Buffer.from(await file.arrayBuffer());
    await fs.promises.writeFile(filePath, buffer);

    stagedFiles.push({
      id: fileId,
      originalName: file.name,
      mimeType: file.type,
      size: file.size,
      order: i,
      relativePath: (file as File & { webkitRelativePath?: string }).webkitRelativePath || undefined,
      stagedPath: filePath,
    });
  }

  const stagedUpload: StagedUploadRecord = {
    id: stagedUploadId,
    userId: args.userId,
    tiktokAccountId: args.tiktokAccountId,
    postType: args.postType,
    files: stagedFiles,
    createdAt,
    expiresAt,
  };

  updateStore((store) => {
    store.stagedUploads.push(stagedUpload);
  });

  return stagedUpload;
}

export async function createBatchAndQueueJobs(args: {
  userId: string;
  tiktokAccountId: string;
  items: Array<{
    stagedUploadId: string;
    postType: UploadPostType;
    caption?: string;
  }>;
}) {
  const now = nowIso();
  const batchId = crypto.randomUUID();

  const batch: UploadBatchRecord = {
    id: batchId,
    userId: args.userId,
    tiktokAccountId: args.tiktokAccountId,
    createdAt: now,
    updatedAt: now,
    status: 'queued',
    totalJobs: args.items.length,
    queuedJobs: args.items.length,
    completedJobs: 0,
    failedJobs: 0,
  };

  const jobs: UploadJobRecord[] = args.items.map((item) => ({
    id: crypto.randomUUID(),
    batchId,
    userId: args.userId,
    tiktokAccountId: args.tiktokAccountId,
    postType: item.postType,
    stagedUploadId: item.stagedUploadId,
    caption: item.caption,
    status: 'queued',
    createdAt: now,
    updatedAt: now,
  }));

  updateStore((store) => {
    store.uploadBatches.push(batch);
    store.uploadJobs.push(...jobs);
  });

  return { batch, jobs };
}

export async function dispatchBatch(batchId: string, concurrency = DEFAULT_DISPATCH_CONCURRENCY) {
  const workers = Math.max(1, Math.min(6, concurrency));

  async function worker() {
    while (true) {
      const job = claimNextQueuedJob(batchId);
      if (!job) {
        return;
      }

      try {
        const result = await processJob(job);
        markJob(job.id, {
          status: 'completed',
          completedAt: nowIso(),
          tiktokPublishId: result.publishId,
          usedVideoFallback: result.usedVideoFallback,
        });
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Upload failed';
        markJob(job.id, {
          status: 'failed',
          failedAt: nowIso(),
          error: message,
        });
      }
    }
  }

  await Promise.all(Array.from({ length: workers }, () => worker()));

  const batch = getStore().uploadBatches.find((item) => item.id === batchId);
  if (batch) {
    recalcBatch(batch);
  }

  return getStore().uploadBatches.find((item) => item.id === batchId);
}

export function getBatchWithJobs(batchId: string) {
  const store = getStore();
  const batch = store.uploadBatches.find((item) => item.id === batchId);
  const jobs = store.uploadJobs.filter((item) => item.batchId === batchId);
  return { batch, jobs };
}
