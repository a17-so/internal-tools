import { NextResponse } from 'next/server';
import { cookies } from 'next/headers';
import { Provider } from '@prisma/client';
import { getProvider } from '@/lib/providers';
import { requireAuth } from '@/lib/auth';
import { db } from '@/lib/db';

export async function GET(request: Request) {
  const appUrl = process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000';

  try {
    const user = await requireAuth();
    const { searchParams } = new URL(request.url);

    const error = searchParams.get('error');
    const errorDescription = searchParams.get('error_description');

    if (error) {
      return NextResponse.redirect(`${appUrl}/accounts?error=${encodeURIComponent(errorDescription || error)}`);
    }

    const code = searchParams.get('code');
    if (!code) {
      return NextResponse.redirect(`${appUrl}/accounts?error=MissingCode`);
    }

    const cookieStore = await cookies();
    const codeVerifier = cookieStore.get('tiktok_code_verifier')?.value;

    const provider = getProvider(Provider.tiktok);
    const account = await provider.connectAccount({
      code,
      codeVerifier,
      redirectUri: `${appUrl}/api/auth/callback`,
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

    const response = NextResponse.redirect(`${appUrl}/accounts?connected=1`);
    response.cookies.delete('tiktok_code_verifier');
    response.cookies.delete('tiktok_auth_state');
    return response;
  } catch (err) {
    console.error('OAuth callback failed:', err);
    return NextResponse.redirect(`${appUrl}/accounts?error=OAuthFailed`);
  }
}
