import { NextResponse } from 'next/server';
import { withAuth } from '@/lib/api-auth';
import { db } from '@/lib/db';
import { getProvider } from '@/lib/providers';

export async function GET(_request: Request, context: { params: Promise<{ accountId: string }> }) {
  return withAuth(async (user) => {
    const { accountId } = await context.params;

    const account = await db.connectedAccount.findFirst({
      where: {
        id: accountId,
        userId: user.id,
      },
    });

    if (!account) {
      return NextResponse.json({ error: 'Account not found' }, { status: 404 });
    }

    const provider = getProvider(account.provider);
    const capabilities = await provider.getCapabilities(account);

    await db.providerCapabilityCache.create({
      data: {
        connectedAccountId: account.id,
        supportsDraftVideo: capabilities.supportsDraftVideo,
        supportsDirectVideo: capabilities.supportsDirectVideo,
        supportsPhotoSlideshow: capabilities.supportsPhotoSlideshow,
        captionLimit: capabilities.captionLimit,
        hashtagLimit: capabilities.hashtagLimit,
        rawJson: JSON.stringify(capabilities.raw || {}),
      },
    });

    return NextResponse.json({ capabilities });
  });
}
