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
    if (!input.accessToken) {
      throw new Error('YouTube connect requires accessToken');
    }

    const me = await fetchMyChannel(input.accessToken);

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
        accessTokenEncrypted: encrypt(input.accessToken),
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
        accessTokenEncrypted: encrypt(input.accessToken),
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

    const accessToken = decrypt(account.accessTokenEncrypted);
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
