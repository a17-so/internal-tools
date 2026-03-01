import fs from 'fs/promises';
import { ConnectedAccount, Provider, UploadAsset, UploadJob, UploadMode, UploadPostType } from '@prisma/client';
import { db } from '@/lib/db';
import { decrypt, encrypt } from '@/lib/crypto';
import { ProviderUploadResult } from '@/lib/types';
import { ProviderError, SocialProvider } from '@/lib/providers/base';

const GRAPH_VERSION = process.env.INSTAGRAM_GRAPH_VERSION || 'v24.0';

async function fetchInstagramUser(accessToken: string, igUserId: string) {
  const fields = 'id,username,name,profile_picture_url';
  const response = await fetch(`https://graph.facebook.com/${GRAPH_VERSION}/${igUserId}?fields=${encodeURIComponent(fields)}&access_token=${encodeURIComponent(accessToken)}`);
  const data = await response.json();
  if (!response.ok || data?.error) {
    throw new Error(data?.error?.message || 'Failed to fetch Instagram account profile');
  }
  return data;
}

async function waitForContainerReady(accessToken: string, creationId: string) {
  for (let i = 0; i < 20; i += 1) {
    const response = await fetch(
      `https://graph.facebook.com/${GRAPH_VERSION}/${creationId}?fields=status_code,status&access_token=${encodeURIComponent(accessToken)}`
    );
    const data = await response.json();

    if (!response.ok || data?.error) {
      throw new Error(data?.error?.message || 'Failed to poll Instagram media container status');
    }

    const statusCode = String(data?.status_code || data?.status || '').toUpperCase();
    if (statusCode === 'FINISHED' || statusCode === 'PUBLISHED') {
      return;
    }

    if (statusCode === 'ERROR' || statusCode === 'EXPIRED') {
      throw new Error(`Instagram media container failed with status: ${statusCode}`);
    }

    await new Promise((resolve) => setTimeout(resolve, 2000));
  }

  throw new Error('Instagram media container timed out before ready status');
}

async function uploadReelVideo(accessToken: string, igUserId: string, videoAsset: UploadAsset, caption: string) {
  const initResponse = await fetch(`https://graph.facebook.com/${GRAPH_VERSION}/${igUserId}/media`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: new URLSearchParams({
      media_type: 'REELS',
      upload_type: 'resumable',
      caption,
      access_token: accessToken,
    }),
  });

  const initData = await initResponse.json();
  if (!initResponse.ok || initData?.error) {
    throw new Error(initData?.error?.message || 'Failed to initialize Instagram reel upload');
  }

  const creationId = String(initData?.id || '');
  const uploadUrl = String(initData?.uri || initData?.upload_url || '');

  if (!creationId || !uploadUrl) {
    throw new Error('Instagram upload initialization did not return required upload URL');
  }

  const fileBytes = await fs.readFile(videoAsset.filePath);
  const uploadResponse = await fetch(uploadUrl, {
    method: 'POST',
    headers: {
      Authorization: `OAuth ${accessToken}`,
      offset: '0',
      file_size: `${fileBytes.length}`,
      'Content-Type': videoAsset.mimeType || 'video/mp4',
    },
    body: new Uint8Array(fileBytes),
  });

  const uploadText = await uploadResponse.text();
  if (!uploadResponse.ok) {
    throw new Error(`Failed to upload Instagram video bytes: ${uploadText}`);
  }

  await waitForContainerReady(accessToken, creationId);

  const publishResponse = await fetch(`https://graph.facebook.com/${GRAPH_VERSION}/${igUserId}/media_publish`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: new URLSearchParams({
      creation_id: creationId,
      access_token: accessToken,
    }),
  });

  const publishData = await publishResponse.json();
  if (!publishResponse.ok || publishData?.error) {
    throw new Error(publishData?.error?.message || 'Failed to publish Instagram reel');
  }

  return {
    externalPostId: String(publishData?.id || ''),
    raw: {
      creationId,
      publishData,
      uploadResponseText: uploadText,
    },
  } satisfies ProviderUploadResult;
}

export const instagramProvider: SocialProvider = {
  provider: Provider.instagram,

  async connectAccount(input) {
    if (!input.accessToken || !input.externalAccountId) {
      throw new Error('Instagram connect requires accessToken and externalAccountId');
    }

    const profile = await fetchInstagramUser(input.accessToken, input.externalAccountId);

    const account = await db.connectedAccount.upsert({
      where: {
        provider_externalAccountId: {
          provider: Provider.instagram,
          externalAccountId: input.externalAccountId,
        },
      },
      update: {
        userId: input.userId,
        username: input.username || profile.username || null,
        displayName: input.displayName || profile.name || profile.username || null,
        avatarUrl: profile.profile_picture_url || null,
        accessTokenEncrypted: encrypt(input.accessToken),
        metadataJson: JSON.stringify({
          ...input.metadata,
          ig_user_id: input.externalAccountId,
        }),
      },
      create: {
        userId: input.userId,
        provider: Provider.instagram,
        externalAccountId: input.externalAccountId,
        username: input.username || profile.username || null,
        displayName: input.displayName || profile.name || profile.username || null,
        avatarUrl: profile.profile_picture_url || null,
        accessTokenEncrypted: encrypt(input.accessToken),
        metadataJson: JSON.stringify({
          ...input.metadata,
          ig_user_id: input.externalAccountId,
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
      captionLimit: 2200,
      hashtagLimit: 30,
      raw: { provider: 'instagram_graph' },
    };
  },

  async upload(job: UploadJob, account: ConnectedAccount, assets: UploadAsset[]): Promise<ProviderUploadResult> {
    if (job.mode !== UploadMode.direct) {
      throw new Error('Instagram provider only supports direct publishing mode');
    }

    if (job.postType !== UploadPostType.video) {
      throw new Error('Instagram provider currently supports only video/Reels uploads');
    }

    const videoAsset = assets.find((asset) => asset.type === 'video');
    if (!videoAsset) {
      throw new Error('Video asset missing for Instagram upload');
    }

    const accessToken = decrypt(account.accessTokenEncrypted);
    return uploadReelVideo(accessToken, account.externalAccountId, videoAsset, job.caption);
  },

  normalizeError(error: unknown): ProviderError {
    const message = error instanceof Error ? error.message : 'Unknown Instagram upload error';

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
