import { NextResponse } from 'next/server';
import { cookies } from 'next/headers';
import crypto from 'crypto';
import { requireCurrentUser } from '@/lib/auth';
import { updateStore } from '@/lib/datastore';

export async function GET(request: Request) {
    const appUrl = (process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000').replace(/\/+$/, '');
    const { searchParams } = new URL(request.url);

    // TikTok may redirect with an error instead of a code
    const error = searchParams.get('error');
    const errorDescription = searchParams.get('error_description');
    if (error) {
        console.error('TikTok returned an error:', error, errorDescription);
        return NextResponse.redirect(
            `${appUrl}?error=${encodeURIComponent(error)}&error_description=${encodeURIComponent(errorDescription || '')}`
        );
    }

    const code = searchParams.get('code');
    const state = searchParams.get('state');

    if (!code) {
        console.error('No code parameter received. Full URL:', request.url);
        return NextResponse.redirect(`${appUrl}?error=NoCode`);
    }

    const cookieStore = await cookies();
    const expectedState = cookieStore.get('tiktok_auth_state')?.value;
    const codeVerifier = cookieStore.get('tiktok_code_verifier')?.value;
    const authUserId = cookieStore.get('tiktok_auth_user_id')?.value;
    const sessionContext = await requireCurrentUser();

    if (!sessionContext || !authUserId || sessionContext.user.id !== authUserId) {
        return NextResponse.redirect(`${appUrl}?error=Unauthorized`);
    }

    if (!expectedState || !state || expectedState !== state) {
        return NextResponse.redirect(`${appUrl}?error=StateMismatch`);
    }

    console.log('Callback received. code:', code?.substring(0, 10) + '...', 'state:', state, 'has codeVerifier:', !!codeVerifier);

    const clientKey = process.env.TIKTOK_CLIENT_KEY;
    const clientSecret = process.env.TIKTOK_CLIENT_SECRET;
    const redirectUri = `${appUrl}/api/auth/callback`;

    try {
        const bodyParams: Record<string, string> = {
            client_key: clientKey as string,
            client_secret: clientSecret as string,
            code,
            grant_type: 'authorization_code',
            redirect_uri: redirectUri,
        };

        if (codeVerifier) {
            bodyParams.code_verifier = codeVerifier;
        }

        console.log('Requesting token with redirect_uri:', redirectUri);

        const tokenResponse = await fetch('https://open.tiktokapis.com/v2/oauth/token/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: new URLSearchParams(bodyParams),
        });

        const data = await tokenResponse.json();
        console.log('TikTok token response status:', tokenResponse.status, 'body:', JSON.stringify(data));

        // TikTok often returns 200 with error info in the body
        if (data.error || data.error_code || !data.access_token) {
            console.error('TikTok Auth Error:', JSON.stringify(data));
            return NextResponse.redirect(
                `${appUrl}?error=AuthFailed&detail=${encodeURIComponent(data.error_description || data.message || JSON.stringify(data))}`
            );
        }

        if (!data.open_id) {
            return NextResponse.redirect(`${appUrl}?error=MissingOpenId`);
        }

        let displayName = data.open_id as string;
        try {
            const profileResponse = await fetch(
                'https://open.tiktokapis.com/v2/user/info/?fields=display_name,open_id',
                { headers: { Authorization: `Bearer ${data.access_token}` } }
            );
            const profileData = await profileResponse.json();
            if (profileResponse.ok && profileData?.data?.user?.display_name) {
                displayName = profileData.data.user.display_name as string;
            }
        } catch {
            // Keep fallback display name from open_id
        }

        // Success - persist the account for the currently logged in user.
        const now = new Date().toISOString();
        updateStore((store) => {
            const existing = store.tiktokAccounts.find(
                (account) => account.userId === sessionContext.user.id && account.openId === data.open_id
            );

            if (existing) {
                existing.accessToken = data.access_token;
                existing.refreshToken = data.refresh_token;
                existing.accessTokenExpiresAt = data.expires_in ? new Date(Date.now() + data.expires_in * 1000).toISOString() : undefined;
                existing.refreshTokenExpiresAt = data.refresh_expires_in ? new Date(Date.now() + data.refresh_expires_in * 1000).toISOString() : undefined;
                existing.displayName = displayName;
                existing.updatedAt = now;
                return;
            }

            store.tiktokAccounts.push({
                id: crypto.randomUUID(),
                userId: sessionContext.user.id,
                openId: data.open_id,
                displayName,
                accessToken: data.access_token,
                refreshToken: data.refresh_token,
                accessTokenExpiresAt: data.expires_in ? new Date(Date.now() + data.expires_in * 1000).toISOString() : undefined,
                refreshTokenExpiresAt: data.refresh_expires_in ? new Date(Date.now() + data.refresh_expires_in * 1000).toISOString() : undefined,
                source: 'oauth',
                createdAt: now,
                updatedAt: now,
            });
        });

        const response = NextResponse.redirect(appUrl);
        response.cookies.set('tiktok_auth_state', '', { maxAge: 0, path: '/' });
        response.cookies.set('tiktok_code_verifier', '', { maxAge: 0, path: '/' });
        response.cookies.set('tiktok_auth_user_id', '', { maxAge: 0, path: '/' });

        console.log('Auth successful! Redirecting to home.');
        return response;
    } catch (err) {
        console.error('Callback handling failed:', err);
        return NextResponse.redirect(`${appUrl}?error=ServerError`);
    }
}
