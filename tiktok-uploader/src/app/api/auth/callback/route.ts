import { NextResponse } from 'next/server';
import { cookies } from 'next/headers';

export async function GET(request: Request) {
    const { searchParams } = new URL(request.url);

    // TikTok may redirect with an error instead of a code
    const error = searchParams.get('error');
    const errorDescription = searchParams.get('error_description');
    if (error) {
        console.error('TikTok returned an error:', error, errorDescription);
        return NextResponse.redirect(
            `${process.env.NEXT_PUBLIC_APP_URL}?error=${encodeURIComponent(error)}&error_description=${encodeURIComponent(errorDescription || '')}`
        );
    }

    const code = searchParams.get('code');
    const state = searchParams.get('state');

    if (!code) {
        console.error('No code parameter received. Full URL:', request.url);
        return NextResponse.redirect(`${process.env.NEXT_PUBLIC_APP_URL}?error=NoCode`);
    }

    const cookieStore = await cookies();
    const codeVerifier = cookieStore.get('tiktok_code_verifier')?.value;

    console.log('Callback received. code:', code?.substring(0, 10) + '...', 'state:', state, 'has codeVerifier:', !!codeVerifier);

    const clientKey = process.env.TIKTOK_CLIENT_KEY;
    const clientSecret = process.env.TIKTOK_CLIENT_SECRET;
    const redirectUri = `${process.env.NEXT_PUBLIC_APP_URL}/api/auth/callback`;

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
                `${process.env.NEXT_PUBLIC_APP_URL}?error=AuthFailed&detail=${encodeURIComponent(data.error_description || data.message || JSON.stringify(data))}`
            );
        }

        // Success - store the access token in a cookie
        const response = NextResponse.redirect(process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000');

        response.cookies.set('tiktok_access_token', data.access_token, {
            httpOnly: true,
            secure: process.env.NODE_ENV === 'production',
            maxAge: data.expires_in || 86400,
            path: '/',
        });

        response.cookies.set('tiktok_open_id', data.open_id, {
            httpOnly: true,
            secure: process.env.NODE_ENV === 'production',
            maxAge: data.expires_in || 86400,
            path: '/',
        });

        if (data.refresh_token) {
            response.cookies.set('tiktok_refresh_token', data.refresh_token, {
                httpOnly: true,
                secure: process.env.NODE_ENV === 'production',
                maxAge: data.refresh_expires_in || 31536000,
                path: '/',
            });
        }

        console.log('Auth successful! Redirecting to home.');
        return response;
    } catch (err) {
        console.error('Callback handling failed:', err);
        return NextResponse.redirect(`${process.env.NEXT_PUBLIC_APP_URL}?error=ServerError`);
    }
}
