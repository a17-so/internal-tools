import fs from 'fs/promises';
import { ConnectedAccount, Provider, UploadAsset, UploadJob, UploadMode, UploadPostType } from '@prisma/client';
import { db } from '@/lib/db';
import { decrypt, encrypt } from '@/lib/crypto';
import { ProviderUploadResult } from '@/lib/types';
import { ProviderError, SocialProvider } from '@/lib/providers/base';

const GRAPH_VERSION = process.env.FACEBOOK_GRAPH_VERSION || 'v24.0';

async function fetchPageProfile(accessToken: string, pageId: string) {
  const response = await fetch(`https://graph.facebook.com/${GRAPH_VERSION}/${pageId}?fields=id,name,picture&access_token=${encodeURIComponent(accessToken)}`);
  const data = await response.json();
  if (!response.ok || data?.error) {
    throw new Error(data?.error?.message || 'Failed to fetch Facebook page profile');
  }
  return data;
}

async function uploadPageVideo(accessToken: string, pageId: string, videoAsset: UploadAsset, caption: string) {
  const fileBytes = await fs.readFile(videoAsset.filePath);
  const form = new FormData();
  form.set('description', caption.slice(0, 5000));
  form.set('published', 'false');
  form.set('access_token', accessToken);
  form.set('source', new Blob([new Uint8Array(fileBytes)], { type: videoAsset.mimeType || 'video/mp4' }), 'video.mp4');

  const response = await fetch(`https://graph.facebook.com/${GRAPH_VERSION}/${pageId}/videos`, {
    method: 'POST',
    body: form,
  });

  const data = await response.json();
  if (!response.ok || data?.error) {
    throw new Error(data?.error?.message || 'Failed to upload Facebook video');
  }

  return {
    externalPostId: data?.id ? String(data.id) : undefined,
    raw: data,
  } satisfies ProviderUploadResult;
}

export const facebookProvider: SocialProvider = {
  provider: Provider.facebook,

  async connectAccount(input) {
    if (!input.accessToken || !input.externalAccountId) {
      throw new Error('Facebook connect requires accessToken and externalAccountId (page id)');
    }

    const page = await fetchPageProfile(input.accessToken, input.externalAccountId);

    const account = await db.connectedAccount.upsert({
      where: {
        provider_externalAccountId: {
          provider: Provider.facebook,
          externalAccountId: input.externalAccountId,
        },
      },
      update: {
        userId: input.userId,
        username: page.name || null,
        displayName: input.displayName || page.name || null,
        avatarUrl: page.picture?.data?.url || null,
        accessTokenEncrypted: encrypt(input.accessToken),
        metadataJson: JSON.stringify({
          ...input.metadata,
          page_id: input.externalAccountId,
        }),
      },
      create: {
        userId: input.userId,
        provider: Provider.facebook,
        externalAccountId: input.externalAccountId,
        username: page.name || null,
        displayName: input.displayName || page.name || null,
        avatarUrl: page.picture?.data?.url || null,
        accessTokenEncrypted: encrypt(input.accessToken),
        metadataJson: JSON.stringify({
          ...input.metadata,
          page_id: input.externalAccountId,
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
      raw: { provider: 'facebook_graph_api' },
    };
  },

  async upload(job: UploadJob, account: ConnectedAccount, assets: UploadAsset[]): Promise<ProviderUploadResult> {
    if (job.mode !== UploadMode.direct) {
      throw new Error('Facebook provider only supports direct publishing mode');
    }

    if (job.postType !== UploadPostType.video) {
      throw new Error('Facebook provider currently supports only video uploads');
    }

    const videoAsset = assets.find((asset) => asset.type === 'video');
    if (!videoAsset) {
      throw new Error('Video asset missing for Facebook upload');
    }

    const accessToken = decrypt(account.accessTokenEncrypted);
    return uploadPageVideo(accessToken, account.externalAccountId, videoAsset, job.caption);
  },

  normalizeError(error: unknown): ProviderError {
    const message = error instanceof Error ? error.message : 'Unknown Facebook upload error';

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
