import { NextResponse } from 'next/server';
import { cookies } from 'next/headers';
import { Provider } from '@prisma/client';
import { requireAuth } from '@/lib/auth';
import { getProvider } from '@/lib/providers';
import { db } from '@/lib/db';
import { normalizeBaseUrl } from '@/lib/oauth';

export async function GET(request: Request) {
  const appUrl = normalizeBaseUrl(process.env.NEXT_PUBLIC_APP_URL, 'http://localhost:3000');
  try {
    const user = await requireAuth();
    const { searchParams } = new URL(request.url);

    const state = searchParams.get('state') || '';
    const code = searchParams.get('code') || '';
    const err = searchParams.get('error_message') || searchParams.get('error_description') || searchParams.get('error');

    if (err) {
      return NextResponse.redirect(`${appUrl}/accounts?error=${encodeURIComponent(String(err))}`);
    }

    const cookieStore = await cookies();
    const expectedState = cookieStore.get('oauth_instagram_state')?.value || '';
    if (!code || !state || state !== expectedState) {
      return NextResponse.redirect(`${appUrl}/accounts?error=Instagram OAuth state mismatch`);
    }

    const provider = getProvider(Provider.instagram);
    const account = await provider.connectAccount({
      userId: user.id,
      code,
      redirectUri: `${appUrl}/api/auth/instagram/callback`,
      metadata: { connect_method: 'oauth' },
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

    const response = NextResponse.redirect(`${appUrl}/accounts?connected=instagram`);
    response.cookies.delete('oauth_instagram_state');
    return response;
  } catch (error) {
    const msg = error instanceof Error ? error.message : 'Instagram OAuth failed';
    return NextResponse.redirect(`${appUrl}/accounts?error=${encodeURIComponent(msg)}`);
  }
}
