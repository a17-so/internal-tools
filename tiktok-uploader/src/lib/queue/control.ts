import { db } from '@/lib/db';

export type DispatchMode = 'due_only' | 'all_queued';

function normalizeDispatchMode(raw: string | null | undefined): DispatchMode {
  return raw === 'all_queued' ? 'all_queued' : 'due_only';
}

export async function getQueueControl(userId: string) {
  const row = await db.queueControl.upsert({
    where: { userId },
    create: { userId, paused: false, dispatchMode: 'due_only' },
    update: {},
  });

  return {
    paused: row.paused,
    dispatchMode: normalizeDispatchMode(row.dispatchMode),
    updatedAt: row.updatedAt,
  };
}

export async function updateQueueControl(userId: string, input: { paused?: boolean; dispatchMode?: string }) {
  const update: { paused?: boolean; dispatchMode?: string } = {};
  if (typeof input.paused === 'boolean') {
    update.paused = input.paused;
  }
  if (input.dispatchMode) {
    update.dispatchMode = normalizeDispatchMode(input.dispatchMode);
  }

  const row = await db.queueControl.upsert({
    where: { userId },
    create: {
      userId,
      paused: update.paused ?? false,
      dispatchMode: update.dispatchMode ?? 'due_only',
    },
    update,
  });

  return {
    paused: row.paused,
    dispatchMode: normalizeDispatchMode(row.dispatchMode),
    updatedAt: row.updatedAt,
  };
}
