import { NextResponse } from 'next/server';
import { UploadStatus } from '@prisma/client';
import { withAuth } from '@/lib/api-auth';
import { db } from '@/lib/db';
import { dispatchPendingJobs } from '@/lib/queue/dispatch';

export async function POST(_request: Request, context: { params: Promise<{ id: string }> }) {
  return withAuth(async (user) => {
    const { id } = await context.params;

    const updated = await db.uploadJob.updateMany({
      where: {
        id,
        userId: user.id,
        status: { in: [UploadStatus.failed, UploadStatus.canceled] },
      },
      data: {
        status: UploadStatus.queued,
        errorMessage: null,
        startedAt: null,
      },
    });

    if (!updated.count) {
      return NextResponse.json({ error: 'Job not found or not retryable' }, { status: 400 });
    }

    await dispatchPendingJobs();
    return NextResponse.json({ success: true });
  });
}
