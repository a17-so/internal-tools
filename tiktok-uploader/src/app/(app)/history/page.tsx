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
      <div>
        <h2 className="text-2xl font-semibold text-slate-900">History</h2>
        <p className="text-slate-600">Completed and failed upload history.</p>
      </div>
      <JobsTable mode="history" initialJobs={jobs as unknown as JobView[]} />
    </div>
  );
}
