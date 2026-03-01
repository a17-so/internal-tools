import { getOptionalAuth } from '@/lib/auth';
import { db } from '@/lib/db';
import ComposeClient from '@/components/app/compose-client';
import type { ComposeAccount } from '@/components/app/compose-client';

export default async function ComposePage() {
  const user = await getOptionalAuth();
  if (!user) return null;

  const accounts = await db.connectedAccount.findMany({
    where: { userId: user.id },
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
      <section className="panel p-5">
        <h2 className="text-2xl font-semibold">Compose</h2>
        <p className="text-muted-foreground">Build mixed video/slideshow batches and dispatch in one action.</p>
      </section>
      <ComposeClient accounts={accounts as unknown as ComposeAccount[]} />
    </div>
  );
}
