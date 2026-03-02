import { NextResponse } from 'next/server';
import { Provider, UploadMode, UploadPostType, UploadStatus } from '@prisma/client';
import { z } from 'zod';
import { withAuth } from '@/lib/api-auth';
import { db } from '@/lib/db';
import { dispatchPendingJobs } from '@/lib/queue/dispatch';
import { buildJobInputFromFiles, createJob } from '@/lib/queue/jobs';
import { persistBrowserFile } from '@/lib/upload-storage';
import { getProvider } from '@/lib/providers';

const createJsonSchema = z.object({
  connectedAccountId: z.string().min(1),
  provider: z.nativeEnum(Provider).default(Provider.tiktok),
  mode: z.nativeEnum(UploadMode).default(UploadMode.draft),
  postType: z.nativeEnum(UploadPostType),
  caption: z.string().max(2200),
  videoPath: z.string().optional(),
  imagePaths: z.array(z.string()).optional(),
  batchId: z.string().optional(),
  clientRef: z.string().optional(),
  scheduleAt: z.string().optional(),
  sendNow: z.boolean().optional().default(true),
});

async function validateCapability(input: {
  accountId: string;
  userId: string;
  mode: UploadMode;
  postType: UploadPostType;
  caption: string;
}) {
  const account = await db.connectedAccount.findFirst({
    where: {
      id: input.accountId,
      userId: input.userId,
    },
    include: {
      capabilities: { take: 1, orderBy: { fetchedAt: 'desc' } },
    },
  });

  if (!account) {
    throw new Error('Connected account not found');
  }

  const cached = account.capabilities[0];
  const provider = getProvider(account.provider);
  const resolved = cached || (await provider.getCapabilities(account));
  const looksLikeRestrictedTikTokScopes =
    account.provider === Provider.tiktok &&
    !resolved.supportsDraftVideo &&
    !resolved.supportsDirectVideo &&
    !resolved.supportsPhotoSlideshow;

  const capabilities = looksLikeRestrictedTikTokScopes
    ? {
      ...resolved,
      supportsDraftVideo: true,
      supportsPhotoSlideshow: true,
      supportsDirectVideo: false,
      captionLimit: 2200,
    }
    : resolved;

  if (input.mode === UploadMode.direct && !capabilities.supportsDirectVideo) {
    throw new Error('Selected account does not support direct publishing');
  }

  if (input.mode === UploadMode.draft && !capabilities.supportsDraftVideo) {
    throw new Error('Selected account does not support draft uploads');
  }

  if (input.postType === UploadPostType.slideshow && !capabilities.supportsPhotoSlideshow) {
    throw new Error('Selected account does not support photo slideshow uploads');
  }

  if (input.caption.length > capabilities.captionLimit) {
    throw new Error(`Caption exceeds limit (${capabilities.captionLimit})`);
  }

  return account;
}

export async function GET(request: Request) {
  return withAuth(async (user) => {
    const { searchParams } = new URL(request.url);
    const statusParam = searchParams.get('status');
    const batchId = searchParams.get('batchId');

    const statuses = statusParam
      ? statusParam.split(',').map((s) => s.trim()).filter(Boolean) as UploadStatus[]
      : undefined;

    const jobs = await db.uploadJob.findMany({
      where: {
        userId: user.id,
        ...(batchId ? { batchId } : {}),
        ...(statuses && statuses.length > 0 ? { status: { in: statuses } } : {}),
      },
      orderBy: { createdAt: 'desc' },
      include: {
        connectedAccount: true,
        assets: { orderBy: { sortOrder: 'asc' } },
        attempts: { orderBy: { createdAt: 'desc' }, take: 5 },
        notifications: { orderBy: { createdAt: 'desc' }, take: 5 },
      },
    });

    return NextResponse.json({ jobs });
  });
}

export async function POST(request: Request) {
  return withAuth(async (user) => {
    const contentType = request.headers.get('content-type') || '';

    if (contentType.includes('multipart/form-data')) {
      const formData = await request.formData();
      const connectedAccountId = String(formData.get('connectedAccountId') || '');
      const mode = (String(formData.get('mode') || UploadMode.draft) as UploadMode);
      const postType = (String(formData.get('postType') || UploadPostType.video) as UploadPostType);
      const caption = String(formData.get('caption') || '');
      const batchId = formData.get('batchId') ? String(formData.get('batchId')) : undefined;
      const scheduleAtRaw = formData.get('scheduleAt') ? String(formData.get('scheduleAt')) : undefined;
      const scheduleAt = scheduleAtRaw ? new Date(scheduleAtRaw) : null;
      const sendNow = String(formData.get('sendNow') || 'true') !== 'false';

      const account = await validateCapability({
        accountId: connectedAccountId,
        userId: user.id,
        mode,
        postType,
        caption,
      });

      let videoPath: string | undefined;
      let imagePaths: string[] | undefined;

      if (postType === UploadPostType.video) {
        const video = formData.get('video');
        if (!(video instanceof File)) {
          return NextResponse.json({ error: 'Video file is required' }, { status: 400 });
        }

        const persisted = await persistBrowserFile(video, 'video');
        videoPath = persisted.filePath;
      } else {
        const allImages = formData.getAll('images').filter((f): f is File => f instanceof File);
        if (allImages.length < 2 || allImages.length > 35) {
          return NextResponse.json({ error: 'Slideshows require 2-35 images' }, { status: 400 });
        }

        const saved = await Promise.all(allImages.map((img, idx) => persistBrowserFile(img, `slide_${idx}`)));
        imagePaths = saved.map((s) => s.filePath);
      }

      const jobInput = await buildJobInputFromFiles({
        userId: user.id,
        batchId,
        connectedAccountId: account.id,
        provider: account.provider,
        mode,
        postType,
        caption,
        videoPath,
        imagePaths,
        scheduledAt: scheduleAt,
      });

      const { job, duplicate } = await createJob(jobInput);
      if (sendNow) {
        await dispatchPendingJobs({ userId: user.id });
      }

      return NextResponse.json({ job, duplicate });
    }

    const payload = createJsonSchema.parse(await request.json());
    const parsedScheduleAt = payload.scheduleAt ? new Date(payload.scheduleAt) : null;
    if (parsedScheduleAt && Number.isNaN(parsedScheduleAt.getTime())) {
      return NextResponse.json({ error: 'Invalid scheduleAt datetime' }, { status: 400 });
    }
    const account = await validateCapability({
      accountId: payload.connectedAccountId,
      userId: user.id,
      mode: payload.mode,
      postType: payload.postType,
      caption: payload.caption,
    });

    const jobInput = await buildJobInputFromFiles({
      userId: user.id,
      batchId: payload.batchId,
      connectedAccountId: account.id,
      provider: account.provider,
      mode: payload.mode,
      postType: payload.postType,
      caption: payload.caption,
      videoPath: payload.videoPath,
      imagePaths: payload.imagePaths,
      clientRef: payload.clientRef,
      scheduledAt: parsedScheduleAt,
    });

    const { job, duplicate } = await createJob(jobInput);

    if (payload.sendNow) {
      await dispatchPendingJobs({ userId: user.id });
    }

    return NextResponse.json({ job, duplicate });
  });
}
