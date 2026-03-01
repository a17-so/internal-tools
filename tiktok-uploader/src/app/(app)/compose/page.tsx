import { getOptionalAuth } from '@/lib/auth';
import { db } from '@/lib/db';
import ComposeClient from '@/components/app/compose-client';

export default async function ComposePage() {
  const user = await getOptionalAuth();
  if (!user) return null;

  const accounts = await db.connectedAccount.findMany({
    where: { userId: user.id, provider: 'tiktok' },
    include: {
      capabilities: {
        orderBy: { fetchedAt: 'desc' },
        take: 1,
      },
    },
    orderBy: { createdAt: 'desc' },
  });

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-2xl font-semibold text-slate-900">Compose</h2>
        <p className="text-slate-600">Build a mixed batch and dispatch all uploads together.</p>
      </div>
      <ComposeClient accounts={accounts as any} />
    </div>
  );
}
