import { NextResponse } from 'next/server';
import { withAuth } from '@/lib/api-auth';
import { db } from '@/lib/db';

export async function GET(_request: Request, context: { params: Promise<{ id: string }> }) {
  return withAuth(async (user) => {
    const { id } = await context.params;

    const job = await db.uploadJob.findFirst({
      where: {
        id,
        userId: user.id,
      },
      include: {
        connectedAccount: true,
        assets: { orderBy: { sortOrder: 'asc' } },
        attempts: { orderBy: { createdAt: 'desc' } },
      },
    });

    if (!job) {
      return NextResponse.json({ error: 'Job not found' }, { status: 404 });
    }

    return NextResponse.json({ job });
  });
}
