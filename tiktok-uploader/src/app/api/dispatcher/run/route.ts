import { NextResponse } from 'next/server';
import { withAuth } from '@/lib/api-auth';
import { dispatchPendingJobs } from '@/lib/queue/dispatch';

export async function POST() {
  return withAuth(async () => {
    const result = await dispatchPendingJobs();
    return NextResponse.json({ success: true, ...result });
  });
}
