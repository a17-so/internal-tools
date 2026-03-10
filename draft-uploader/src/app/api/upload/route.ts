import { NextResponse } from 'next/server';
import { requireCurrentUser } from '@/lib/auth';
import {
  getStore,
  type StagedUploadRecord,
  type UploadPostType,
} from '@/lib/datastore';
import {
  createBatchAndQueueJobs,
  dispatchBatch,
  getBatchWithJobs,
  stageUpload,
} from '@/lib/upload-service';

type SendAllPayload = {
  action: 'send-all';
  tiktokAccountId?: string;
  concurrency?: number;
  items?: Array<{
    stagedUploadId: string;
    postType: UploadPostType;
    caption?: string;
  }>;
};

type DispatchPayload = {
  action: 'dispatch';
  batchId?: string;
  concurrency?: number;
};

function canUseAccount(userId: string, role: 'admin' | 'user', accountId: string) {
  const store = getStore();
  const account = store.tiktokAccounts.find((item) => item.id === accountId);
  if (!account) {
    return null;
  }

  if (role !== 'admin' && account.userId !== userId) {
    return null;
  }

  return account;
}

function validateStagedOwnership(args: {
  userId: string;
  role: 'admin' | 'user';
  accountId: string;
  items: Array<{ stagedUploadId: string; postType: UploadPostType }>;
}) {
  const store = getStore();
  const stagedMap = new Map<string, StagedUploadRecord>();
  for (const staged of store.stagedUploads) {
    stagedMap.set(staged.id, staged);
  }

  for (const item of args.items) {
    const staged = stagedMap.get(item.stagedUploadId);
    if (!staged) {
      return `Staged upload not found: ${item.stagedUploadId}`;
    }

    if (args.role !== 'admin' && staged.userId !== args.userId) {
      return `Forbidden staged upload: ${item.stagedUploadId}`;
    }

    if (staged.tiktokAccountId !== args.accountId) {
      return `Staged upload account mismatch: ${item.stagedUploadId}`;
    }

    if (staged.postType !== item.postType) {
      return `Post type mismatch for staged upload: ${item.stagedUploadId}`;
    }

    if (staged.postType === 'video' && staged.files.length !== 1) {
      return `Video staged upload must contain one file: ${item.stagedUploadId}`;
    }

    if (staged.postType === 'slideshow' && (staged.files.length < 2 || staged.files.length > 35)) {
      return `Slideshow staged upload must contain 2-35 images: ${item.stagedUploadId}`;
    }
  }

  return null;
}

async function handleStage(formData: FormData, userId: string, role: 'admin' | 'user') {
  const accountId = formData.get('tiktokAccountId');
  const postType = formData.get('postType');

  if (typeof accountId !== 'string' || !accountId) {
    return NextResponse.json({ error: 'A TikTok account must be selected' }, { status: 400 });
  }

  if (postType !== 'video' && postType !== 'slideshow') {
    return NextResponse.json({ error: 'postType must be video or slideshow' }, { status: 400 });
  }

  const account = canUseAccount(userId, role, accountId);
  if (!account) {
    return NextResponse.json({ error: 'TikTok account not found or forbidden' }, { status: 403 });
  }

  const files = postType === 'video'
    ? formData.getAll('video').filter((item): item is File => item instanceof File)
    : formData.getAll('images').filter((item): item is File => item instanceof File);

  if (postType === 'video' && files.length !== 1) {
    return NextResponse.json({ error: 'Video post requires exactly one video file' }, { status: 400 });
  }

  if (postType === 'slideshow' && (files.length < 2 || files.length > 35)) {
    return NextResponse.json({ error: 'Slideshow requires 2 to 35 images' }, { status: 400 });
  }

  const stagedUpload = await stageUpload({
    userId,
    tiktokAccountId: accountId,
    postType,
    files,
  });

  return NextResponse.json({
    stagedUpload: {
      id: stagedUpload.id,
      tiktokAccountId: stagedUpload.tiktokAccountId,
      postType: stagedUpload.postType,
      fileCount: stagedUpload.files.length,
      files: stagedUpload.files.map((file) => ({
        id: file.id,
        name: file.originalName,
        order: file.order,
      })),
      expiresAt: stagedUpload.expiresAt,
    },
  });
}

async function handleSendAll(payload: SendAllPayload, userId: string, role: 'admin' | 'user') {
  if (!payload.tiktokAccountId) {
    return NextResponse.json({ error: 'tiktokAccountId is required' }, { status: 400 });
  }

  const items = Array.isArray(payload.items) ? payload.items : [];
  if (items.length === 0) {
    return NextResponse.json({ error: 'At least one staged item is required' }, { status: 400 });
  }

  const account = canUseAccount(userId, role, payload.tiktokAccountId);
  if (!account) {
    return NextResponse.json({ error: 'TikTok account not found or forbidden' }, { status: 403 });
  }

  const stagedValidation = validateStagedOwnership({
    userId,
    role,
    accountId: payload.tiktokAccountId,
    items,
  });

  if (stagedValidation) {
    return NextResponse.json({ error: stagedValidation }, { status: 400 });
  }

  const { batch, jobs } = await createBatchAndQueueJobs({
    userId,
    tiktokAccountId: payload.tiktokAccountId,
    items,
  });

  const nextBatch = await dispatchBatch(batch.id, payload.concurrency ?? 2);
  const result = getBatchWithJobs(batch.id);

  return NextResponse.json({
    success: true,
    batch: nextBatch ?? result.batch,
    queuedCount: jobs.length,
    jobs: result.jobs.map((job) => ({
      id: job.id,
      postType: job.postType,
      status: job.status,
      tiktokPublishId: job.tiktokPublishId,
      usedVideoFallback: job.usedVideoFallback,
      error: job.error,
    })),
  });
}

async function handleDispatch(payload: DispatchPayload) {
  if (!payload.batchId) {
    return NextResponse.json({ error: 'batchId is required' }, { status: 400 });
  }

  const batch = await dispatchBatch(payload.batchId, payload.concurrency ?? 2);
  const result = getBatchWithJobs(payload.batchId);

  return NextResponse.json({
    success: true,
    batch: batch ?? result.batch,
    jobs: result.jobs,
  });
}

export async function POST(request: Request) {
  try {
    const context = await requireCurrentUser();
    if (!context) {
      return NextResponse.json({ error: 'Unauthorized. Please log in first.' }, { status: 401 });
    }

    const contentType = request.headers.get('content-type') || '';

    if (contentType.includes('multipart/form-data')) {
      const formData = await request.formData();
      const action = formData.get('action');
      if (action !== 'stage') {
        return NextResponse.json({ error: 'Unsupported multipart action' }, { status: 400 });
      }
      return handleStage(formData, context.user.id, context.user.role);
    }

    const payload = await request.json();
    if (payload?.action === 'send-all') {
      return handleSendAll(payload as SendAllPayload, context.user.id, context.user.role);
    }

    if (payload?.action === 'dispatch') {
      return handleDispatch(payload as DispatchPayload);
    }

    return NextResponse.json({ error: 'Unsupported action' }, { status: 400 });
  } catch (error: unknown) {
    console.error('Upload route error:', error);
    const message = error instanceof Error ? error.message : 'Internal Server Error';
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
