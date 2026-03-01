import { NextResponse } from 'next/server';
import { z } from 'zod';
import { withAuth } from '@/lib/api-auth';
import { getProvider } from '@/lib/providers';
import { Provider } from '@prisma/client';
import { db } from '@/lib/db';

const schema = z.object({
  accessToken: z.string().min(1),
  displayName: z.string().optional(),
});

export async function POST(request: Request) {
  return withAuth(async (user) => {
    const input = schema.parse(await request.json());
    const provider = getProvider(Provider.youtube);

    const account = await provider.connectAccount({
      userId: user.id,
      accessToken: input.accessToken,
      displayName: input.displayName,
      metadata: { connect_method: 'token' },
    });

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

    return NextResponse.json({ account, capabilities });
  });
}
