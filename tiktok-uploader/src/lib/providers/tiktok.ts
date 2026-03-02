import fs from 'fs/promises';
import os from 'os';
import path from 'path';
import { execFile } from 'child_process';
import { promisify } from 'util';
import { ConnectedAccount, Provider, UploadAsset, UploadJob, UploadMode, UploadPostType } from '@prisma/client';
import { db } from '@/lib/db';
import { decrypt, encrypt } from '@/lib/crypto';
import { ProviderCapabilities, ProviderUploadResult } from '@/lib/types';
import { ProviderError, SocialProvider } from '@/lib/providers/base';

const execFileAsync = promisify(execFile);

function parseJsonSafely(value: string | null | undefined): unknown {
  if (!value) return null;
  try {
    return JSON.parse(value);
  } catch {
    return null;
  }
}

async function getUserInfo(accessToken: string) {
  const fieldSets = [
    'open_id,union_id,avatar_url,display_name,username',
    'open_id,union_id,avatar_url,display_name',
    'open_id',
  ];

  let lastError = 'Unable to fetch TikTok user info';
  for (const fields of fieldSets) {
    const response = await fetch(`https://open.tiktokapis.com/v2/user/info/?fields=${fields}`, {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
    });

    const data = await response.json();
    if (response.ok && data?.error?.code === 'ok') {
      return data?.data?.user;
    }

    lastError = data?.error?.message || lastError;
  }

  throw new Error(lastError);
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

async function refreshAccessToken(refreshToken: string) {
  const clientKey = process.env.TIKTOK_CLIENT_KEY;
  const clientSecret = process.env.TIKTOK_CLIENT_SECRET;
  if (!clientKey || !clientSecret) {
    throw new Error('TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET are required');
  }

  const response = await fetch('https://open.tiktokapis.com/v2/oauth/token/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: new URLSearchParams({
      client_key: clientKey,
      client_secret: clientSecret,
      grant_type: 'refresh_token',
      refresh_token: refreshToken,
    }),
  });

  const data = await response.json();
  if (!response.ok || data?.error || !data?.access_token) {
    throw new Error(data?.error_description || data?.error || 'Failed to refresh TikTok access token');
  }

  return data as {
    access_token: string;
    refresh_token?: string;
    expires_in?: number;
    refresh_expires_in?: number;
  };
}

async function getValidAccessToken(account: ConnectedAccount) {
  const tokenExpiredSoon = account.tokenExpiresAt !== null && account.tokenExpiresAt.getTime() <= Date.now() + 1000 * 60 * 2;
  if (!tokenExpiredSoon) {
    return decrypt(account.accessTokenEncrypted);
  }

  if (!account.refreshTokenEncrypted) {
    throw new Error('TikTok token expired and no refresh token is available. Reconnect account.');
  }

  if (account.refreshExpiresAt && account.refreshExpiresAt.getTime() <= Date.now()) {
    throw new Error('TikTok refresh token expired. Reconnect account.');
  }

  const refreshToken = decrypt(account.refreshTokenEncrypted);
  const refreshed = await refreshAccessToken(refreshToken);
  await db.connectedAccount.update({
    where: { id: account.id },
    data: {
      accessTokenEncrypted: encrypt(refreshed.access_token),
      refreshTokenEncrypted: refreshed.refresh_token ? encrypt(refreshed.refresh_token) : account.refreshTokenEncrypted,
      tokenExpiresAt: refreshed.expires_in ? new Date(Date.now() + refreshed.expires_in * 1000) : null,
      refreshExpiresAt: refreshed.refresh_expires_in ? new Date(Date.now() + refreshed.refresh_expires_in * 1000) : account.refreshExpiresAt,
    },
  });

  return refreshed.access_token;
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

async function requestJson(url: string, accessToken: string, payload: unknown) {
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${accessToken}`,
      'Content-Type': 'application/json; charset=UTF-8',
    },
    body: JSON.stringify(payload),
  });
  const data = await response.json().catch(() => ({}));
  return { response, data };
}

async function initializeSlideshowUpload(accessToken: string, mode: UploadMode, caption: string, imageCount: number) {
  const tries = [
    {
      label: 'inbox-photo-init',
      endpoint: mode === UploadMode.draft
        ? 'https://open.tiktokapis.com/v2/post/publish/inbox/photo/init/'
        : 'https://open.tiktokapis.com/v2/post/publish/photo/init/',
      payload: {
        post_info: { title: caption },
        source_info: { source: 'FILE_UPLOAD', photo_count: imageCount },
      },
    },
    {
      label: 'content-init-photo',
      endpoint: 'https://open.tiktokapis.com/v2/post/publish/content/init/',
      payload: {
        post_info: {
          title: caption,
          post_mode: mode === UploadMode.draft ? 'MEDIA_UPLOAD_TO_INBOX' : 'DIRECT_POST',
          media_type: 'PHOTO',
        },
        source_info: {
          source: 'FILE_UPLOAD',
          photo_count: imageCount,
        },
      },
    },
  ] as const;

  const errors: string[] = [];

  for (const attempt of tries) {
    const { response, data } = await requestJson(attempt.endpoint, accessToken, attempt.payload);
    const hasProviderError = Boolean(data?.error?.code && data?.error?.code !== 'ok');
    const uploadUrls = Array.isArray(data?.data?.upload_urls) ? data.data.upload_urls : [];

    if (response.ok && !hasProviderError && uploadUrls.length > 0) {
      return data.data;
    }

    errors.push(
      `${attempt.label}: ${data?.error?.message || data?.error?.code || response.status || 'unknown_error'}`
    );
  }

  throw new Error(`TikTok slideshow init failed across known endpoints: ${errors.join(' | ')}`);
}

async function createSlideshowVideoFallback(imageAssets: UploadAsset[]) {
  const tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), 'uploader-slideshow-'));
  const concatFilePath = path.join(tmpDir, 'frames.txt');
  const outPath = path.join(tmpDir, `slideshow_${Date.now()}.mp4`);
  const frameSeconds = Number(process.env.SLIDESHOW_FALLBACK_FRAME_SECONDS || 1.2);

  try {
    const lines: string[] = [];
    for (const asset of imageAssets) {
      lines.push(`file '${asset.filePath.replace(/'/g, "'\\''")}'`);
      lines.push(`duration ${frameSeconds}`);
    }
    const lastAsset = imageAssets[imageAssets.length - 1];
    lines.push(`file '${lastAsset.filePath.replace(/'/g, "'\\''")}'`);
    await fs.writeFile(concatFilePath, `${lines.join('\n')}\n`, 'utf8');

    await execFileAsync('ffmpeg', [
      '-y',
      '-f', 'concat',
      '-safe', '0',
      '-i', concatFilePath,
      '-vf', 'scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2',
      '-r', '30',
      '-pix_fmt', 'yuv420p',
      outPath,
    ]);

    return outPath;
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    throw new Error(`Slideshow fallback video generation failed. Ensure ffmpeg is installed. ${message}`);
  } finally {
    await fs.rm(concatFilePath, { force: true }).catch(() => undefined);
  }
}

export const tiktokProvider: SocialProvider = {
  provider: Provider.tiktok,

  async connectAccount(input) {
    if (!input.code) {
      throw new Error('TikTok connect requires authorization code');
    }

    const tokenData = await exchangeCodeForToken({
      code: input.code,
      codeVerifier: input.codeVerifier,
      redirectUri: input.redirectUri || getRedirectUri(),
    });

    if (!tokenData.open_id) {
      throw new Error('TikTok token exchange missing open_id');
    }

    let userInfo: Awaited<ReturnType<typeof getUserInfo>> | null = null;
    try {
      userInfo = await getUserInfo(tokenData.access_token);
    } catch (error) {
      // In sandbox/review, apps may only have minimal scopes and user profile fetch can fail.
      // We can still connect the account using open_id from token exchange.
      console.warn('TikTok user info fetch failed; continuing with token open_id only', error);
    }

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
    const accessToken = await getValidAccessToken(account);

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

      try {
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
          raw: {
            ...initData,
            fallbackUsed: false,
          },
        };
      } catch (slideshowError) {
        const fallbackMode = (process.env.TIKTOK_SLIDESHOW_FALLBACK || 'video').toLowerCase();
        if (fallbackMode !== 'video') {
          throw slideshowError;
        }

        const fallbackVideoPath = await createSlideshowVideoFallback(imageAssets);
        const fallbackVideo = await fs.readFile(fallbackVideoPath);
        const uploadUrl = await initializeVideoUpload(accessToken, job.mode, job.caption, fallbackVideo.length);
        if (!uploadUrl) {
          throw new Error('TikTok fallback video upload URL missing');
        }

        await uploadBinaryToUrl(uploadUrl, fallbackVideo, 'video/mp4');
        await fs.rm(fallbackVideoPath, { force: true }).catch(() => undefined);

        return {
          raw: {
            fallbackUsed: true,
            fallbackReason: slideshowError instanceof Error ? slideshowError.message : 'unknown slideshow init error',
            fallbackType: 'video',
          },
        };
      }
    }

    throw new Error(`Unsupported post type: ${job.postType}`);
  },

  normalizeError(error: unknown): ProviderError {
    const message = error instanceof Error ? error.message : 'Unknown TikTok upload error';

    if (/unsupported|requires|invalid|not support|caption exceeds|a slideshow requires/i.test(message)) {
      return {
        message,
        retryable: false,
        raw: error,
      };
    }

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
