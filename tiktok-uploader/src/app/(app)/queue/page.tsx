import JobsTable from '@/components/app/jobs-table';
import QueueControls from '@/components/app/queue-controls';
import type { JobView } from '@/components/app/jobs-table';
import { getOptionalAuth } from '@/lib/auth';
import { db } from '@/lib/db';
import { getQueueControl } from '@/lib/queue/control';

export default async function QueuePage() {
  const user = await getOptionalAuth();
  if (!user) return null;

  const jobs = await db.uploadJob.findMany({
    where: {
      userId: user.id,
      status: { in: ['queued', 'running', 'failed'] },
    },
    orderBy: { createdAt: 'desc' },
    include: {
      connectedAccount: true,
    },
    take: 200,
  });
  const control = await getQueueControl(user.id);

  return (
    <div className="space-y-4">
      <section className="panel p-5">
        <h2 className="text-2xl font-semibold">Queue</h2>
        <p className="text-muted-foreground">Monitor active batches, pause processing, and drain due jobs safely.</p>
      </section>
      <QueueControls initialControl={{ ...control, updatedAt: control.updatedAt.toISOString() }} />
      <JobsTable mode="queue" initialJobs={jobs as unknown as JobView[]} />
    </div>
  );
}
