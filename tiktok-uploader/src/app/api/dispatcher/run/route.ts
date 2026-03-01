import { NextResponse } from 'next/server';
import { withAuth } from '@/lib/api-auth';
import { getQueueControl } from '@/lib/queue/control';
import { dispatchPendingJobs } from '@/lib/queue/dispatch';

export async function POST(request: Request) {
  return withAuth(async (user) => {
    const body = await request.json().catch(() => ({} as { mode?: string; forcePaused?: boolean }));
    const control = await getQueueControl(user.id);
    const mode = body.mode === 'all_queued' || body.mode === 'due_only'
      ? body.mode
      : control.dispatchMode;
    const result = await dispatchPendingJobs({
      userId: user.id,
      ignoreSchedule: mode === 'all_queued',
      forcePaused: Boolean(body.forcePaused),
    });
    return NextResponse.json({ success: true, ...result });
  });
}
