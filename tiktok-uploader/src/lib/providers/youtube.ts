import fs from 'fs/promises';
import { ConnectedAccount, Provider, UploadAsset, UploadJob, UploadMode, UploadPostType } from '@prisma/client';
import { db } from '@/lib/db';
import { decrypt, encrypt } from '@/lib/crypto';
import { ProviderUploadResult } from '@/lib/types';
import { ProviderError, SocialProvider } from '@/lib/providers/base';

async function fetchMyChannel(accessToken: string) {
  const response = await fetch('https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true', {
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });

  const data = await response.json();
  if (!response.ok || data?.error) {
    throw new Error(data?.error?.message || 'Failed to fetch YouTube channel profile');
  }

  const item = data?.items?.[0];
  if (!item?.id) {
    throw new Error('No YouTube channel found for provided token');
  }

  return {
    channelId: String(item.id),
    title: String(item.snippet?.title || ''),
    customUrl: String(item.snippet?.customUrl || ''),
    thumbnails: item.snippet?.thumbnails,
  };
}

async function exchangeCodeForToken(code: string, redirectUri?: string) {
  const clientId = process.env.YOUTUBE_CLIENT_ID || process.env.GOOGLE_CLIENT_ID;
  const clientSecret = process.env.YOUTUBE_CLIENT_SECRET || process.env.GOOGLE_CLIENT_SECRET;
  const callback = redirectUri || `${process.env.NEXT_PUBLIC_APP_URL}/api/auth/youtube/callback`;

  if (!clientId || !clientSecret) {
    throw new Error('YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET are required');
  }

  const response = await fetch('https://oauth2.googleapis.com/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      code,
      client_id: clientId,
      client_secret: clientSecret,
      redirect_uri: callback,
      grant_type: 'authorization_code',
    }),
  });

  const data = await response.json();
  if (!response.ok || data?.error) {
    throw new Error(data?.error_description || data?.error || 'Failed to exchange YouTube OAuth code');
  }

  return data as { access_token: string; refresh_token?: string; expires_in?: number };
}

async function refreshAccessToken(refreshToken: string) {
  const clientId = process.env.YOUTUBE_CLIENT_ID || process.env.GOOGLE_CLIENT_ID;
  const clientSecret = process.env.YOUTUBE_CLIENT_SECRET || process.env.GOOGLE_CLIENT_SECRET;
  if (!clientId || !clientSecret) {
    throw new Error('YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET are required');
  }

  const response = await fetch('https://oauth2.googleapis.com/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      refresh_token: refreshToken,
      client_id: clientId,
      client_secret: clientSecret,
      grant_type: 'refresh_token',
    }),
  });

  const data = await response.json();
  if (!response.ok || data?.error) {
    throw new Error(data?.error_description || data?.error || 'Failed to refresh YouTube access token');
  }

  return data as { access_token: string; expires_in?: number };
}

async function getValidAccessToken(account: ConnectedAccount) {
  const needsRefresh =
    account.tokenExpiresAt !== null &&
    account.tokenExpiresAt.getTime() <= Date.now() + 1000 * 60 * 2;

  if (!needsRefresh) {
    return decrypt(account.accessTokenEncrypted);
  }

  if (!account.refreshTokenEncrypted) {
    throw new Error('YouTube token expired and no refresh token is available. Reconnect account.');
  }

  const refreshed = await refreshAccessToken(decrypt(account.refreshTokenEncrypted));
  await db.connectedAccount.update({
    where: { id: account.id },
    data: {
      accessTokenEncrypted: encrypt(refreshed.access_token),
      tokenExpiresAt: refreshed.expires_in ? new Date(Date.now() + refreshed.expires_in * 1000) : null,
    },
  });

  return refreshed.access_token;
}

async function initResumableUpload(accessToken: string, title: string, description: string) {
  const response = await fetch('https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${accessToken}`,
      'Content-Type': 'application/json; charset=UTF-8',
      'X-Upload-Content-Type': 'video/mp4',
    },
    body: JSON.stringify({
      snippet: {
        title: title.slice(0, 100),
        description: description.slice(0, 5000),
      },
      status: {
        privacyStatus: 'private',
      },
    }),
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Failed to initialize YouTube upload: ${body}`);
  }

  const location = response.headers.get('location');
  if (!location) {
    throw new Error('YouTube resumable upload did not return location header');
  }

  return location;
}

async function uploadVideoBytes(uploadUrl: string, fileBytes: Buffer, mimeType: string) {
  const response = await fetch(uploadUrl, {
    method: 'PUT',
    headers: {
      'Content-Type': mimeType || 'video/mp4',
      'Content-Length': `${fileBytes.length}`,
    },
    body: new Uint8Array(fileBytes),
  });

  const text = await response.text();
  if (!response.ok) {
    throw new Error(`YouTube video upload failed: ${text}`);
  }

  try {
    return JSON.parse(text);
  } catch {
    return {};
  }
}

export const youtubeProvider: SocialProvider = {
  provider: Provider.youtube,

  async connectAccount(input) {
    let accessToken = input.accessToken || '';
    let refreshToken: string | undefined;
    let tokenExpiresAt: Date | null = null;

    if (input.code) {
      const token = await exchangeCodeForToken(input.code, input.redirectUri);
      accessToken = token.access_token;
      refreshToken = token.refresh_token;
      tokenExpiresAt = token.expires_in ? new Date(Date.now() + token.expires_in * 1000) : null;
    }

    if (!accessToken) {
      throw new Error('YouTube connect requires OAuth code or accessToken');
    }

    const me = await fetchMyChannel(accessToken);

    const account = await db.connectedAccount.upsert({
      where: {
        provider_externalAccountId: {
          provider: Provider.youtube,
          externalAccountId: me.channelId,
        },
      },
      update: {
        userId: input.userId,
        username: me.customUrl || null,
        displayName: input.displayName || me.title || null,
        avatarUrl: me.thumbnails?.default?.url || null,
        accessTokenEncrypted: encrypt(accessToken),
        refreshTokenEncrypted: refreshToken ? encrypt(refreshToken) : undefined,
        tokenExpiresAt,
        metadataJson: JSON.stringify({
          ...input.metadata,
          channel_id: me.channelId,
          custom_url: me.customUrl,
        }),
      },
      create: {
        userId: input.userId,
        provider: Provider.youtube,
        externalAccountId: me.channelId,
        username: me.customUrl || null,
        displayName: input.displayName || me.title || null,
        avatarUrl: me.thumbnails?.default?.url || null,
        accessTokenEncrypted: encrypt(accessToken),
        refreshTokenEncrypted: refreshToken ? encrypt(refreshToken) : null,
        tokenExpiresAt,
        metadataJson: JSON.stringify({
          ...input.metadata,
          channel_id: me.channelId,
          custom_url: me.customUrl,
        }),
      },
    });

    return account;
  },

  async getCapabilities() {
    return {
      supportsDraftVideo: false,
      supportsDirectVideo: true,
      supportsPhotoSlideshow: false,
      captionLimit: 5000,
      hashtagLimit: 30,
      raw: { provider: 'youtube_data_api' },
    };
  },

  async upload(job: UploadJob, account: ConnectedAccount, assets: UploadAsset[]): Promise<ProviderUploadResult> {
    if (job.mode !== UploadMode.direct) {
      throw new Error('YouTube provider only supports direct publishing mode');
    }

    if (job.postType !== UploadPostType.video) {
      throw new Error('YouTube provider currently supports only video uploads');
    }

    const videoAsset = assets.find((asset) => asset.type === 'video');
    if (!videoAsset) {
      throw new Error('Video asset missing for YouTube upload');
    }

    const accessToken = await getValidAccessToken(account);
    const fileBytes = await fs.readFile(videoAsset.filePath);

    const uploadUrl = await initResumableUpload(accessToken, job.caption || 'Short', job.caption || '');
    const result = await uploadVideoBytes(uploadUrl, fileBytes, videoAsset.mimeType || 'video/mp4');

    return {
      externalPostId: result?.id ? String(result.id) : undefined,
      raw: result,
    };
  },

  normalizeError(error: unknown): ProviderError {
    const message = error instanceof Error ? error.message : 'Unknown YouTube upload error';

    const retryable =
      /timeout|network|temporar|rate|429|5\d\d/i.test(message) ||
      /ECONN|ENOTFOUND|ETIMEDOUT/i.test(message);

    return {
      message,
      retryable,
      raw: error,
    };
  },
};
