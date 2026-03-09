import { NextResponse } from 'next/server';
import crypto from 'crypto';

export async function GET() {
    const clientKey = process.env.TIKTOK_CLIENT_KEY;
    const appUrl = (process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000').replace(/\/+$/, '');
    const redirectUri = `${appUrl}/api/auth/callback`;
    const scopes = (process.env.TIKTOK_OAUTH_SCOPES || 'user.info.basic,user.info.profile,user.info.stats,video.list,video.upload')
      .split(',')
      .map((scope) => scope.trim())
      .filter(Boolean)
      .join(',');

    if (!clientKey) {
        return NextResponse.redirect(`${appUrl}?error=MissingClientKey`);
    }

    // Create a random string for state to prevent CSRF
    const state = Math.random().toString(36).substring(7);

    // PKCE Code Verifier & Challenge
    const codeVerifier = crypto.randomBytes(32).toString('base64url');
    const codeChallenge = crypto.createHash('sha256').update(codeVerifier).digest('base64url');

    const response = NextResponse.redirect(
        `https://www.tiktok.com/v2/auth/authorize/?client_key=${clientKey}&response_type=code&scope=${scopes}&redirect_uri=${encodeURIComponent(redirectUri)}&state=${state}&code_challenge=${codeChallenge}&code_challenge_method=S256`
    );

    response.cookies.set('tiktok_auth_state', state, {
        httpOnly: true,
        secure: process.env.NODE_ENV === 'production',
        maxAge: 60 * 10, // 10 minutes
        path: '/',
    });

    response.cookies.set('tiktok_code_verifier', codeVerifier, {
        httpOnly: true,
        secure: process.env.NODE_ENV === 'production',
        maxAge: 60 * 10, // 10 minutes
        path: '/',
    });

    return response;
}
