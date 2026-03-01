import { getOptionalAuth } from '@/lib/auth';
import { db } from '@/lib/db';
import AccountsClient from '@/components/app/accounts-client';
import type { AccountView } from '@/components/app/accounts-client';

export default async function AccountsPage() {
  const user = await getOptionalAuth();
  if (!user) return null;

  const accounts = await db.connectedAccount.findMany({
    where: { userId: user.id },
    orderBy: { createdAt: 'desc' },
    include: {
      capabilities: {
        orderBy: { fetchedAt: 'desc' },
        take: 1,
      },
    },
  });

  const initialAccounts: AccountView[] = accounts.map((account) => ({
    id: account.id,
    provider: account.provider,
    username: account.username,
    displayName: account.displayName,
    externalAccountId: account.externalAccountId,
    tokenExpiresAt: account.tokenExpiresAt ? account.tokenExpiresAt.toISOString() : null,
    capabilities: account.capabilities.map((cap) => ({
      supportsDraftVideo: cap.supportsDraftVideo,
      supportsDirectVideo: cap.supportsDirectVideo,
      supportsPhotoSlideshow: cap.supportsPhotoSlideshow,
    })),
  }));

  return <AccountsClient initialAccounts={initialAccounts} />;
}
