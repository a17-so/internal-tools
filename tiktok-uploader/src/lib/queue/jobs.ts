import crypto from 'crypto';
import fs from 'fs/promises';
import { Provider, UploadAssetType, UploadMode, UploadPostType, UploadStatus } from '@prisma/client';
import { db } from '@/lib/db';
import { buildIdempotencyKey, isLikelyMimeType } from '@/lib/queue/idempotency';
import { QueueCreateJobInput } from '@/lib/types';

export async function hashFile(path: string): Promise<string> {
  const file = await fs.readFile(path);
  return crypto.createHash('sha256').update(file).digest('hex');
}

export async function createBatch(params: { userId: string; name?: string }) {
  return db.uploadBatch.create({
    data: {
      userId: params.userId,
      name: params.name,
      status: UploadStatus.queued,
    },
  });
}

export async function createJob(input: QueueCreateJobInput) {
  const existing = await db.uploadJob.findFirst({
    where: {
      userId: input.userId,
      idempotencyKey: input.idempotencyKey,
      createdAt: { gt: new Date(Date.now() - 1000 * 60 * 60 * 24) },
    },
  });

  if (existing) {
    return { job: existing, duplicate: true };
  }

  const job = await db.uploadJob.create({
    data: {
      userId: input.userId,
      batchId: input.batchId,
      connectedAccountId: input.connectedAccountId,
      provider: input.provider,
      mode: input.mode,
      postType: input.postType,
      caption: input.caption,
      status: UploadStatus.queued,
      idempotencyKey: input.idempotencyKey,
      assets: {
        create: input.assets.map((asset) => ({
          type: asset.type === 'video' ? UploadAssetType.video : UploadAssetType.image,
          filePath: asset.filePath,
          mimeType: asset.mimeType,
          sizeBytes: asset.sizeBytes,
          sortOrder: asset.sortOrder,
        })),
      },
    },
    include: { assets: true },
  });

  return { job, duplicate: false };
}

export async function buildJobInputFromFiles(input: {
  userId: string;
  batchId?: string;
  connectedAccountId: string;
  provider?: Provider;
  mode: UploadMode;
  postType: UploadPostType;
  caption: string;
  videoPath?: string;
  imagePaths?: string[];
  clientRef?: string;
}) {
  const provider = input.provider ?? Provider.tiktok;

  const assets = [] as Array<{
    type: 'video' | 'image';
    filePath: string;
    mimeType: string;
    sizeBytes: number;
    sortOrder: number;
    hash: string;
  }>;

  if (input.postType === UploadPostType.video) {
    if (!input.videoPath) {
      throw new Error('videoPath is required for video posts');
    }

    const stat = await fs.stat(input.videoPath);
    if (!stat.isFile()) {
      throw new Error(`Not a file: ${input.videoPath}`);
    }

    assets.push({
      type: 'video',
      filePath: input.videoPath,
      mimeType: isLikelyMimeType(input.videoPath),
      sizeBytes: stat.size,
      sortOrder: 0,
      hash: await hashFile(input.videoPath),
    });
  } else {
    const images = input.imagePaths || [];
    if (images.length < 2 || images.length > 35) {
      throw new Error('Slideshows must contain 2-35 images');
    }

    for (let i = 0; i < images.length; i += 1) {
      const imagePath = images[i];
      const stat = await fs.stat(imagePath);
      if (!stat.isFile()) {
        throw new Error(`Not a file: ${imagePath}`);
      }

      assets.push({
        type: 'image',
        filePath: imagePath,
        mimeType: isLikelyMimeType(imagePath),
        sizeBytes: stat.size,
        sortOrder: i,
        hash: await hashFile(imagePath),
      });
    }
  }

  const idempotencyKey = buildIdempotencyKey({
    mediaHashes: assets.map((a) => a.hash),
    caption: input.caption,
    accountId: input.connectedAccountId,
    provider,
    mode: input.mode,
    postType: input.postType,
    clientRef: input.clientRef,
  });

  return {
    userId: input.userId,
    batchId: input.batchId,
    connectedAccountId: input.connectedAccountId,
    provider,
    mode: input.mode,
    postType: input.postType,
    caption: input.caption,
    idempotencyKey,
    assets: assets.map((asset) => ({
      type: asset.type,
      filePath: asset.filePath,
      mimeType: asset.mimeType,
      sizeBytes: asset.sizeBytes,
      sortOrder: asset.sortOrder,
    })),
  };
}
