import { NextResponse } from 'next/server';
import { cookies } from 'next/headers';
import { Provider } from '@prisma/client';
import { requireAuth } from '@/lib/auth';
import { getProvider } from '@/lib/providers';
import { db } from '@/lib/db';

export async function GET(request: Request) {
  const appUrl = process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000';
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
    const expectedState = cookieStore.get('oauth_facebook_state')?.value || '';
    if (!code || !state || state !== expectedState) {
      return NextResponse.redirect(`${appUrl}/accounts?error=Facebook OAuth state mismatch`);
    }

    const provider = getProvider(Provider.facebook);
    const account = await provider.connectAccount({
      userId: user.id,
      code,
      redirectUri: `${appUrl}/api/auth/facebook/callback`,
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

    const response = NextResponse.redirect(`${appUrl}/accounts?connected=facebook`);
    response.cookies.delete('oauth_facebook_state');
    return response;
  } catch (error) {
    const msg = error instanceof Error ? error.message : 'Facebook OAuth failed';
    return NextResponse.redirect(`${appUrl}/accounts?error=${encodeURIComponent(msg)}`);
  }
}
