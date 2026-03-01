import { NextResponse } from 'next/server';
import { UploadMode, UploadPostType } from '@prisma/client';
import { z } from 'zod';
import { withAuth } from '@/lib/api-auth';
import { createBatch, buildJobInputFromFiles, createJob } from '@/lib/queue/jobs';
import { dispatchPendingJobs } from '@/lib/queue/dispatch';

const itemSchema = z.object({
  connectedAccountId: z.string().min(1),
  mode: z.nativeEnum(UploadMode).default(UploadMode.draft),
  postType: z.nativeEnum(UploadPostType),
  caption: z.string().max(2200),
  videoPath: z.string().optional(),
  imagePaths: z.array(z.string()).optional(),
  clientRef: z.string().optional(),
  scheduleAt: z.string().optional(),
});

const schema = z.object({
  name: z.string().max(120).optional(),
  jobs: z.array(itemSchema).default([]),
  sendNow: z.boolean().default(true),
});

export async function POST(request: Request) {
  return withAuth(async (user) => {
    const payload = schema.parse(await request.json());

    const batch = await createBatch({ userId: user.id, name: payload.name });

    const results = [] as Array<{ id: string; duplicate: boolean }>;

    for (const item of payload.jobs) {
      const parsedScheduleAt = item.scheduleAt ? new Date(item.scheduleAt) : null;
      if (parsedScheduleAt && Number.isNaN(parsedScheduleAt.getTime())) {
        return NextResponse.json({ error: `Invalid scheduleAt datetime in batch item (${item.connectedAccountId})` }, { status: 400 });
      }

      const jobInput = await buildJobInputFromFiles({
        userId: user.id,
        batchId: batch.id,
        connectedAccountId: item.connectedAccountId,
        mode: item.mode,
        postType: item.postType,
        caption: item.caption,
        videoPath: item.videoPath,
        imagePaths: item.imagePaths,
        clientRef: item.clientRef,
        scheduledAt: parsedScheduleAt,
      });

      const { job, duplicate } = await createJob(jobInput);
      results.push({ id: job.id, duplicate });
    }

    if (payload.sendNow && payload.jobs.length > 0) {
      await dispatchPendingJobs();
    }

    return NextResponse.json({ batch, jobs: results });
  });
}
