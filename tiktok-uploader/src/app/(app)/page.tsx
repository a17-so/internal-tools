import Link from 'next/link';
import { ArrowRight, Clock3, Layers, PlayCircle, TriangleAlert } from 'lucide-react';
import { db } from '@/lib/db';
import { getOptionalAuth } from '@/lib/auth';
import { Button } from '@/components/ui/button';

export default async function DashboardPage() {
  const user = await getOptionalAuth();
  if (!user) return null;

  const [accountCount, queuedCount, runningCount, failedCount, recentJobs] = await Promise.all([
    db.connectedAccount.count({ where: { userId: user.id } }),
    db.uploadJob.count({ where: { userId: user.id, status: 'queued' } }),
    db.uploadJob.count({ where: { userId: user.id, status: 'running' } }),
    db.uploadJob.count({ where: { userId: user.id, status: 'failed' } }),
    db.uploadJob.findMany({
      where: { userId: user.id },
      include: { connectedAccount: true },
      orderBy: { createdAt: 'desc' },
      take: 8,
    }),
  ]);

  const cards = [
    { label: 'Connected Accounts', value: accountCount, icon: Layers, tone: 'text-indigo-700 bg-indigo-50 border-indigo-100' },
    { label: 'Queued Jobs', value: queuedCount, icon: Clock3, tone: 'text-amber-700 bg-amber-50 border-amber-100' },
    { label: 'Running Jobs', value: runningCount, icon: PlayCircle, tone: 'text-sky-700 bg-sky-50 border-sky-100' },
    { label: 'Failed Jobs', value: failedCount, icon: TriangleAlert, tone: 'text-rose-700 bg-rose-50 border-rose-100' },
  ];

  return (
    <div className="space-y-4">
      <section className="panel overflow-hidden p-5">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Publishing Control</p>
        <div className="mt-2 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-3xl font-semibold text-slate-900">Upload faster with fewer clicks</h2>
            <p className="mt-1 text-slate-600">Queue mixed media posts, route to any connected account, and dispatch with guardrails.</p>
          </div>
          <div className="flex gap-2">
            <Button asChild className="rounded-xl">
              <Link href="/compose">Create Batch</Link>
            </Button>
            <Button asChild variant="outline" className="rounded-xl">
              <Link href="/queue">Open Queue</Link>
            </Button>
          </div>
        </div>
      </section>

      <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {cards.map((card) => {
          const Icon = card.icon;
          return (
            <div key={card.label} className="panel p-4">
              <div className={`inline-flex rounded-xl border p-2 ${card.tone}`}>
                <Icon className="h-4 w-4" />
              </div>
              <p className="mt-3 text-sm text-slate-500">{card.label}</p>
              <p className="text-3xl font-semibold text-slate-900">{card.value}</p>
            </div>
          );
        })}
      </section>

      <section className="panel overflow-hidden p-4">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-base font-semibold text-slate-900">Recent Activity</h3>
          <Button asChild variant="ghost" size="sm" className="rounded-xl">
            <Link href="/history">
              View all
              <ArrowRight className="h-4 w-4" />
            </Link>
          </Button>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-[0.08em] text-slate-500">
                <th className="py-2">Status</th>
                <th className="py-2">Type</th>
                <th className="py-2">Account</th>
                <th className="py-2">Created</th>
              </tr>
            </thead>
            <tbody>
              {recentJobs.map((job) => (
                <tr key={job.id} className="border-t border-slate-100 text-slate-700">
                  <td className="py-2">
                    <span className={`status-pill status-${job.status}`}>{job.status}</span>
                  </td>
                  <td className="py-2">{job.postType}/{job.mode}</td>
                  <td className="py-2">{job.connectedAccount.displayName || job.connectedAccount.username || '-'}</td>
                  <td className="py-2 text-slate-500">{new Date(job.createdAt).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
