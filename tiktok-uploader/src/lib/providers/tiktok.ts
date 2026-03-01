import fs from 'fs/promises';
import { ConnectedAccount, Provider, UploadAsset, UploadJob, UploadMode, UploadPostType } from '@prisma/client';
import { db } from '@/lib/db';
import { decrypt, encrypt } from '@/lib/crypto';
import { ProviderCapabilities, ProviderUploadResult } from '@/lib/types';
import { ProviderError, SocialProvider } from '@/lib/providers/base';

function parseJsonSafely(value: string | null | undefined): unknown {
  if (!value) return null;
  try {
    return JSON.parse(value);
  } catch {
    return null;
  }
}

async function getUserInfo(accessToken: string) {
  const response = await fetch('https://open.tiktokapis.com/v2/user/info/?fields=open_id,union_id,avatar_url,display_name,username', {
    method: 'GET',
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });

  const data = await response.json();
  if (!response.ok || data?.error?.code !== 'ok') {
    throw new Error(data?.error?.message || 'Unable to fetch TikTok user info');
  }

  return data?.data?.user;
}

function getRedirectUri() {
  const url = process.env.NEXT_PUBLIC_APP_URL;
  if (!url) {
    throw new Error('NEXT_PUBLIC_APP_URL is required');
  }

  return `${url}/api/auth/callback`;
}

async function exchangeCodeForToken(input: { code: string; codeVerifier?: string; redirectUri: string }) {
  const clientKey = process.env.TIKTOK_CLIENT_KEY;
  const clientSecret = process.env.TIKTOK_CLIENT_SECRET;

  if (!clientKey || !clientSecret) {
    throw new Error('TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET are required');
  }

  const bodyParams: Record<string, string> = {
    client_key: clientKey,
    client_secret: clientSecret,
    code: input.code,
    grant_type: 'authorization_code',
    redirect_uri: input.redirectUri,
  };

  if (input.codeVerifier) {
    bodyParams.code_verifier = input.codeVerifier;
  }

  const tokenResponse = await fetch('https://open.tiktokapis.com/v2/oauth/token/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: new URLSearchParams(bodyParams),
  });

  const data = await tokenResponse.json();
  if (!tokenResponse.ok || data.error || !data.access_token) {
    throw new Error(data?.error_description || data?.error || 'TikTok token exchange failed');
  }

  return data;
}

async function initializeVideoUpload(accessToken: string, mode: UploadMode, title: string, videoSize: number) {
  const endpoint = mode === UploadMode.draft
    ? 'https://open.tiktokapis.com/v2/post/publish/inbox/video/init/'
    : 'https://open.tiktokapis.com/v2/post/publish/video/init/';

  const response = await fetch(endpoint, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${accessToken}`,
      'Content-Type': 'application/json; charset=UTF-8',
    },
    body: JSON.stringify({
      source_info: {
        source: 'FILE_UPLOAD',
        video_size: videoSize,
        chunk_size: videoSize,
        total_chunk_count: 1,
      },
      post_info: {
        title,
      },
    }),
  });

  const data = await response.json();
  if (!response.ok || (data?.error?.code && data.error.code !== 'ok')) {
    throw new Error(data?.error?.message || 'Failed to initialize TikTok video upload');
  }

  return data?.data?.upload_url as string | undefined;
}

async function uploadBinaryToUrl(uploadUrl: string, payload: Buffer, mimeType: string) {
  const body = new Uint8Array(payload);
  const response = await fetch(uploadUrl, {
    method: 'PUT',
    headers: {
      'Content-Range': `bytes 0-${payload.length - 1}/${payload.length}`,
      'Content-Type': mimeType,
      'Content-Length': payload.length.toString(),
    },
    body,
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Binary upload failed: ${body}`);
  }
}

async function initializeSlideshowUpload(accessToken: string, mode: UploadMode, caption: string, imageCount: number) {
  // API shape intentionally abstracted behind provider. Endpoint support can vary by app review scope.
  const endpoint = mode === UploadMode.draft
    ? 'https://open.tiktokapis.com/v2/post/publish/inbox/photo/init/'
    : 'https://open.tiktokapis.com/v2/post/publish/photo/init/';

  const response = await fetch(endpoint, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${accessToken}`,
      'Content-Type': 'application/json; charset=UTF-8',
    },
    body: JSON.stringify({
      post_info: {
        title: caption,
      },
      source_info: {
        source: 'FILE_UPLOAD',
        photo_count: imageCount,
      },
    }),
  });

  const data = await response.json();
  if (!response.ok || (data?.error?.code && data.error.code !== 'ok')) {
    throw new Error(data?.error?.message || 'Failed to initialize TikTok slideshow upload');
  }

  return data?.data;
}

export const tiktokProvider: SocialProvider = {
  provider: Provider.tiktok,

  async connectAccount(input) {
    const tokenData = await exchangeCodeForToken({
      code: input.code,
      codeVerifier: input.codeVerifier,
      redirectUri: input.redirectUri || getRedirectUri(),
    });

    const userInfo = await getUserInfo(tokenData.access_token);

    const account = await db.connectedAccount.upsert({
      where: {
        provider_externalAccountId: {
          provider: Provider.tiktok,
          externalAccountId: tokenData.open_id,
        },
      },
      update: {
        userId: input.userId,
        username: userInfo?.username || null,
        displayName: userInfo?.display_name || null,
        avatarUrl: userInfo?.avatar_url || null,
        accessTokenEncrypted: encrypt(tokenData.access_token),
        refreshTokenEncrypted: tokenData.refresh_token ? encrypt(tokenData.refresh_token) : null,
        tokenExpiresAt: tokenData.expires_in ? new Date(Date.now() + tokenData.expires_in * 1000) : null,
        refreshExpiresAt: tokenData.refresh_expires_in ? new Date(Date.now() + tokenData.refresh_expires_in * 1000) : null,
        metadataJson: JSON.stringify({
          open_id: tokenData.open_id,
          scope: tokenData.scope,
          union_id: userInfo?.union_id,
        }),
      },
      create: {
        userId: input.userId,
        provider: Provider.tiktok,
        externalAccountId: tokenData.open_id,
        username: userInfo?.username || null,
        displayName: userInfo?.display_name || null,
        avatarUrl: userInfo?.avatar_url || null,
        accessTokenEncrypted: encrypt(tokenData.access_token),
        refreshTokenEncrypted: tokenData.refresh_token ? encrypt(tokenData.refresh_token) : null,
        tokenExpiresAt: tokenData.expires_in ? new Date(Date.now() + tokenData.expires_in * 1000) : null,
        refreshExpiresAt: tokenData.refresh_expires_in ? new Date(Date.now() + tokenData.refresh_expires_in * 1000) : null,
        metadataJson: JSON.stringify({
          open_id: tokenData.open_id,
          scope: tokenData.scope,
          union_id: userInfo?.union_id,
        }),
      },
    });

    return account;
  },

  async getCapabilities(account) {
    const meta = parseJsonSafely(account.metadataJson) as { scope?: string } | null;
    const scopes = (meta?.scope || '').split(',').map((s) => s.trim());

    // Conservative defaults based on granted scopes; adjust once account-level checks are available.
    const capabilities: ProviderCapabilities = {
      supportsDraftVideo: scopes.includes('video.upload') || scopes.length === 0,
      supportsDirectVideo: scopes.includes('video.publish'),
      supportsPhotoSlideshow: scopes.includes('video.upload') || scopes.includes('photo.upload') || scopes.length === 0,
      captionLimit: 2200,
      hashtagLimit: 30,
      raw: { scopes },
    };

    return capabilities;
  },

  async upload(job: UploadJob, account: ConnectedAccount, assets: UploadAsset[]): Promise<ProviderUploadResult> {
    const accessToken = decrypt(account.accessTokenEncrypted);

    if (job.postType === UploadPostType.video) {
      const videoAsset = assets.find((asset) => asset.type === 'video');
      if (!videoAsset) {
        throw new Error('Video asset missing');
      }

      const data = await fs.readFile(videoAsset.filePath);
      const uploadUrl = await initializeVideoUpload(accessToken, job.mode, job.caption, data.length);
      if (!uploadUrl) {
        throw new Error('TikTok video upload URL missing');
      }

      await uploadBinaryToUrl(uploadUrl, data, videoAsset.mimeType || 'video/mp4');
      return {
        raw: { uploadUrl },
      };
    }

    if (job.postType === UploadPostType.slideshow) {
      const imageAssets = assets
        .filter((asset) => asset.type === 'image')
        .sort((a, b) => a.sortOrder - b.sortOrder);

      if (imageAssets.length < 2) {
        throw new Error('A slideshow requires at least 2 images');
      }

      const initData = await initializeSlideshowUpload(accessToken, job.mode, job.caption, imageAssets.length);
      const uploadUrls = Array.isArray(initData?.upload_urls) ? initData.upload_urls : [];

      if (uploadUrls.length !== imageAssets.length) {
        throw new Error('TikTok slideshow API did not return the expected upload URLs');
      }

      for (let i = 0; i < imageAssets.length; i += 1) {
        const asset = imageAssets[i];
        const uploadUrl = uploadUrls[i];
        const data = await fs.readFile(asset.filePath);
        await uploadBinaryToUrl(uploadUrl, data, asset.mimeType || 'image/jpeg');
      }

      return {
        raw: initData,
      };
    }

    throw new Error(`Unsupported post type: ${job.postType}`);
  },

  normalizeError(error: unknown): ProviderError {
    const message = error instanceof Error ? error.message : 'Unknown TikTok upload error';

    const retryable =
      /timeout|network|rate|429|5\d\d|temporar/i.test(message) ||
      /ECONN|ENOTFOUND|ETIMEDOUT/i.test(message);

    return {
      message,
      retryable,
      raw: error,
    };
  },
};
