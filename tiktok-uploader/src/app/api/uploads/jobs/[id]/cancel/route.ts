import { NextResponse } from 'next/server';
import { UploadStatus } from '@prisma/client';
import { withAuth } from '@/lib/api-auth';
import { db } from '@/lib/db';

export async function POST(_request: Request, context: { params: Promise<{ id: string }> }) {
  return withAuth(async (user) => {
    const { id } = await context.params;

    const updated = await db.uploadJob.updateMany({
      where: {
        id,
        userId: user.id,
        status: { in: [UploadStatus.queued, UploadStatus.running] },
      },
      data: {
        status: UploadStatus.canceled,
        completedAt: new Date(),
      },
    });

    if (!updated.count) {
      return NextResponse.json({ error: 'Job not found or already final' }, { status: 400 });
    }

    return NextResponse.json({ success: true });
  });
}
