import { Provider, UploadStatus } from '@prisma/client';
import { db } from '@/lib/db';
import { notifyJobFailed } from '@/lib/notifications';
import { getProvider } from '@/lib/providers';
import { getQueueControl } from '@/lib/queue/control';
import { getRetryDelayMs, getRetryPolicy } from '@/lib/queue/retry-policy';

const GLOBAL_CONCURRENCY = Number(process.env.QUEUE_GLOBAL_CONCURRENCY || 5);
const ACCOUNT_CONCURRENCY = Number(process.env.QUEUE_ACCOUNT_CONCURRENCY || 2);

function nowMinus(ms: number) {
  return new Date(Date.now() - ms);
}

async function recalcBatch(batchId: string) {
  const jobs = await db.uploadJob.findMany({
    where: { batchId },
    select: { status: true },
  });

  const summary = {
    totalJobs: jobs.length,
    queuedJobs: jobs.filter((j) => j.status === UploadStatus.queued).length,
    runningJobs: jobs.filter((j) => j.status === UploadStatus.running).length,
    succeededJobs: jobs.filter((j) => j.status === UploadStatus.succeeded).length,
    failedJobs: jobs.filter((j) => j.status === UploadStatus.failed).length,
    canceledJobs: jobs.filter((j) => j.status === UploadStatus.canceled).length,
  };

  let status: UploadStatus = UploadStatus.queued;
  if (summary.runningJobs > 0) {
    status = UploadStatus.running;
  } else if (summary.failedJobs > 0 && summary.queuedJobs === 0) {
    status = UploadStatus.failed;
  } else if (summary.succeededJobs === summary.totalJobs && summary.totalJobs > 0) {
    status = UploadStatus.succeeded;
  }

  await db.uploadBatch.update({
    where: { id: batchId },
    data: {
      ...summary,
      status,
    },
  });
}

async function processJob(jobId: string) {
  const job = await db.uploadJob.findUnique({
    where: { id: jobId },
    include: {
      connectedAccount: true,
      assets: {
        orderBy: { sortOrder: 'asc' },
      },
    },
  });

  if (!job || job.status !== UploadStatus.running) {
    return;
  }

  const provider = getProvider(job.provider);
  const attemptNo = job.attemptCount;

  try {
    const result = await provider.upload(job, job.connectedAccount, job.assets);

    await db.uploadAttempt.create({
      data: {
        uploadJobId: job.id,
        attemptNo,
        message: 'Upload succeeded',
        payloadJson: JSON.stringify(result.raw || {}),
      },
    });

    await db.uploadJob.update({
      where: { id: job.id },
      data: {
        status: UploadStatus.succeeded,
        completedAt: new Date(),
        providerPostId: result.externalPostId || null,
        errorMessage: null,
        nextAttemptAt: null,
      },
    });
  } catch (error) {
    const normalized = provider.normalizeError(error);
    const retryPolicy = getRetryPolicy(job.provider);
    const maxRetries = job.maxRetries || retryPolicy.maxRetries;
    const shouldRetry = normalized.retryable && job.attemptCount < maxRetries;

    await db.uploadAttempt.create({
      data: {
        uploadJobId: job.id,
        attemptNo,
        httpStatus: normalized.httpStatus,
        providerCode: normalized.providerCode,
        message: normalized.message,
        payloadJson: JSON.stringify(normalized.raw || {}),
      },
    });

    if (shouldRetry) {
      const delayMs = getRetryDelayMs(job.provider, job.attemptCount);
      await db.uploadJob.update({
        where: { id: job.id },
        data: {
          status: UploadStatus.queued,
          errorMessage: normalized.message,
          startedAt: null,
          maxRetries,
          nextAttemptAt: new Date(Date.now() + delayMs),
        },
      });
    } else {
      await db.uploadJob.update({
        where: { id: job.id },
        data: {
          status: UploadStatus.failed,
          errorMessage: normalized.message,
          completedAt: new Date(),
          nextAttemptAt: null,
          maxRetries,
        },
      });
      await notifyJobFailed(job, normalized.message);
    }
  } finally {
    if (job.batchId) {
      await recalcBatch(job.batchId);
    }
  }
}

async function claimNextJobs(limit: number, options: { userId?: string; ignoreSchedule?: boolean; forcePaused?: boolean }) {
  const now = new Date();

  if (options.userId) {
    const control = await getQueueControl(options.userId);
    if (control.paused && !options.forcePaused) {
      return [];
    }
  }

  const scheduleClause = options.ignoreSchedule
    ? {}
    : {
      OR: [
        { scheduledAt: null },
        { scheduledAt: { lte: now } },
      ],
    };

  const queuedJobs = await db.uploadJob.findMany({
    where: {
      status: UploadStatus.queued,
      ...(options.userId ? { userId: options.userId } : {}),
      OR: [
        { startedAt: null },
        { startedAt: { lt: nowMinus(1000 * 60 * 5) } },
      ],
      AND: [
        {
          OR: [
            { nextAttemptAt: null },
            { nextAttemptAt: { lte: now } },
          ],
        },
        scheduleClause,
      ],
    },
    orderBy: { createdAt: 'asc' },
    take: limit,
    select: {
      id: true,
      connectedAccountId: true,
      attemptCount: true,
      maxRetries: true,
      batchId: true,
      provider: true,
    },
  });

  const claimed: { id: string; connectedAccountId: string; batchId: string | null }[] = [];

  for (const job of queuedJobs) {
    const policy = getRetryPolicy(job.provider as Provider);
    const maxRetries = job.maxRetries || policy.maxRetries;

    if (job.attemptCount >= maxRetries) {
      await db.uploadJob.update({
        where: { id: job.id },
        data: {
          status: UploadStatus.failed,
          errorMessage: 'Retry limit reached',
          maxRetries,
        },
      });
      if (job.batchId) {
        await recalcBatch(job.batchId);
      }
      continue;
    }

    const updated = await db.uploadJob.updateMany({
      where: {
        id: job.id,
        status: UploadStatus.queued,
      },
      data: {
        status: UploadStatus.running,
        startedAt: new Date(),
        attemptCount: { increment: 1 },
        maxRetries,
      },
    });

    if (updated.count > 0) {
      claimed.push({ id: job.id, connectedAccountId: job.connectedAccountId, batchId: job.batchId });
      if (job.batchId) {
        await recalcBatch(job.batchId);
      }
    }
  }

  return claimed;
}

export async function dispatchPendingJobs(options?: { userId?: string; ignoreSchedule?: boolean; forcePaused?: boolean }) {
  const claimed = await claimNextJobs(100, options || {});
  if (claimed.length === 0) return { processed: 0 };

  const accountInFlight = new Map<string, number>();
  const queue = [...claimed];
  const running = new Set<Promise<void>>();

  const runOne = async (jobId: string, accountId: string) => {
    accountInFlight.set(accountId, (accountInFlight.get(accountId) || 0) + 1);
    try {
      await processJob(jobId);
    } finally {
      accountInFlight.set(accountId, Math.max(0, (accountInFlight.get(accountId) || 1) - 1));
    }
  };

  while (queue.length > 0 || running.size > 0) {
    while (running.size < GLOBAL_CONCURRENCY && queue.length > 0) {
      const index = queue.findIndex((j) => (accountInFlight.get(j.connectedAccountId) || 0) < ACCOUNT_CONCURRENCY);
      if (index === -1) break;

      const [next] = queue.splice(index, 1);
      const promise = runOne(next.id, next.connectedAccountId).finally(() => {
        running.delete(promise);
      });
      running.add(promise);
    }

    if (running.size === 0) break;
    await Promise.race(running);
  }

  return { processed: claimed.length };
}
