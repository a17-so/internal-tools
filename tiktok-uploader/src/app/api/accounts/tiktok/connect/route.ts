import { NextResponse } from 'next/server';
import { z } from 'zod';
import { withAuth } from '@/lib/api-auth';
import { getProvider } from '@/lib/providers';
import { Provider } from '@prisma/client';
import { db } from '@/lib/db';

const schema = z.object({
  code: z.string().min(1),
  codeVerifier: z.string().optional(),
  redirectUri: z.string().url().optional(),
});

export async function POST(request: Request) {
  return withAuth(async (user) => {
    const input = schema.parse(await request.json());
    const provider = getProvider(Provider.tiktok);

    const account = await provider.connectAccount({
      code: input.code,
      codeVerifier: input.codeVerifier,
      redirectUri: input.redirectUri || `${process.env.NEXT_PUBLIC_APP_URL}/api/auth/callback`,
      userId: user.id,
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
