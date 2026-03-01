import { NextResponse } from 'next/server';
import { z } from 'zod';
import { withAuth } from '@/lib/api-auth';
import { getQueueControl, updateQueueControl } from '@/lib/queue/control';

export async function GET() {
  return withAuth(async (user) => {
    const control = await getQueueControl(user.id);
    return NextResponse.json({ control });
  });
}

const schema = z.object({
  paused: z.boolean().optional(),
  dispatchMode: z.enum(['due_only', 'all_queued']).optional(),
});

export async function POST(request: Request) {
  return withAuth(async (user) => {
    const input = schema.parse(await request.json());
    const control = await updateQueueControl(user.id, input);
    return NextResponse.json({ control });
  });
}
