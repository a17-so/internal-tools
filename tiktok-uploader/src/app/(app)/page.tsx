import { db } from '@/lib/db';
import { getOptionalAuth } from '@/lib/auth';

export default async function DashboardPage() {
  const user = await getOptionalAuth();
  if (!user) return null;

  const [accountCount, queuedCount, runningCount, failedCount] = await Promise.all([
    db.connectedAccount.count({ where: { userId: user.id } }),
    db.uploadJob.count({ where: { userId: user.id, status: 'queued' } }),
    db.uploadJob.count({ where: { userId: user.id, status: 'running' } }),
    db.uploadJob.count({ where: { userId: user.id, status: 'failed' } }),
  ]);

  const cards = [
    { label: 'Connected Accounts', value: accountCount },
    { label: 'Queued Jobs', value: queuedCount },
    { label: 'Running Jobs', value: runningCount },
    { label: 'Failed Jobs', value: failedCount },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold text-slate-900">Publishing Dashboard</h2>
        <p className="text-slate-600">Draft-first, multi-account upload pipeline for TikTok.</p>
      </div>
      <div className="grid gap-4 md:grid-cols-4">
        {cards.map((card) => (
          <div key={card.label} className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-sm text-slate-500">{card.label}</p>
            <p className="text-3xl font-semibold text-slate-900">{card.value}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
