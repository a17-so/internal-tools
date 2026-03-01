import JobsTable from '@/components/app/jobs-table';
import type { JobView } from '@/components/app/jobs-table';
import { getOptionalAuth } from '@/lib/auth';
import { db } from '@/lib/db';

export default async function HistoryPage() {
  const user = await getOptionalAuth();
  if (!user) return null;

  const jobs = await db.uploadJob.findMany({
    where: {
      userId: user.id,
      status: { in: ['succeeded', 'failed', 'canceled'] },
    },
    orderBy: { createdAt: 'desc' },
    include: {
      connectedAccount: true,
    },
    take: 200,
  });

  return (
    <div className="space-y-4">
      <section className="panel p-5">
        <h2 className="text-2xl font-semibold">History</h2>
        <p className="text-muted-foreground">Audit completed, failed, and canceled jobs with quick search.</p>
      </section>
      <JobsTable mode="history" initialJobs={jobs as unknown as JobView[]} />
    </div>
  );
}
