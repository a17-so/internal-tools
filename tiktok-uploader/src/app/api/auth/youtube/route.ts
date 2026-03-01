import { NextResponse } from 'next/server';
import { requireAuth } from '@/lib/auth';

export async function GET() {
  await requireAuth();

  const clientId = process.env.YOUTUBE_CLIENT_ID || process.env.GOOGLE_CLIENT_ID;
  const appUrl = process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000';
  if (!clientId) {
    return NextResponse.redirect(`${appUrl}/accounts?error=Missing YOUTUBE_CLIENT_ID`);
  }

  const redirectUri = `${appUrl}/api/auth/youtube/callback`;
  const state = Math.random().toString(36).slice(2);

  const authUrl =
    'https://accounts.google.com/o/oauth2/v2/auth?' +
    new URLSearchParams({
      client_id: clientId,
      redirect_uri: redirectUri,
      response_type: 'code',
      scope: 'https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly',
      access_type: 'offline',
      prompt: 'consent',
      state,
    }).toString();

  const response = NextResponse.redirect(authUrl);
  response.cookies.set('oauth_youtube_state', state, { httpOnly: true, path: '/', sameSite: 'lax' });
  return response;
}
