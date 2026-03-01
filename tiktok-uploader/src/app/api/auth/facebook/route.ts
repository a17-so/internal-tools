import { NextResponse } from 'next/server';
import { requireAuth } from '@/lib/auth';

export async function GET() {
  await requireAuth();

  const appId = process.env.FACEBOOK_APP_ID;
  const appUrl = process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000';
  if (!appId) {
    return NextResponse.redirect(`${appUrl}/accounts?error=Missing FACEBOOK_APP_ID`);
  }

  const redirectUri = `${appUrl}/api/auth/facebook/callback`;
  const state = Math.random().toString(36).slice(2);

  const authUrl =
    `https://www.facebook.com/${process.env.FACEBOOK_GRAPH_VERSION || 'v24.0'}/dialog/oauth?` +
    new URLSearchParams({
      client_id: appId,
      redirect_uri: redirectUri,
      state,
      response_type: 'code',
      scope: 'pages_show_list,pages_read_engagement,pages_manage_posts',
    }).toString();

  const response = NextResponse.redirect(authUrl);
  response.cookies.set('oauth_facebook_state', state, { httpOnly: true, path: '/', sameSite: 'lax' });
  return response;
}
