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

async function exchangeCodeForUserToken(code: string, redirectUri?: string) {
  const clientId = process.env.INSTAGRAM_APP_ID || process.env.FACEBOOK_APP_ID;
  const clientSecret = process.env.INSTAGRAM_APP_SECRET || process.env.FACEBOOK_APP_SECRET;
  const callback = redirectUri || `${process.env.NEXT_PUBLIC_APP_URL}/api/auth/instagram/callback`;

  if (!clientId || !clientSecret) {
    throw new Error('INSTAGRAM_APP_ID and INSTAGRAM_APP_SECRET are required');
  }

  const tokenResp = await fetch(
    `https://graph.facebook.com/${GRAPH_VERSION}/oauth/access_token?` +
    new URLSearchParams({
      client_id: clientId,
      client_secret: clientSecret,
      redirect_uri: callback,
      code,
    }).toString()
  );
  const tokenData = await tokenResp.json();
  if (!tokenResp.ok || tokenData?.error) {
    throw new Error(tokenData?.error?.message || 'Failed to exchange Instagram OAuth code');
  }

  const shortToken = String(tokenData.access_token || '');
  if (!shortToken) {
    throw new Error('Instagram OAuth exchange did not return access token');
  }

  const longResp = await fetch(
    `https://graph.facebook.com/${GRAPH_VERSION}/oauth/access_token?` +
    new URLSearchParams({
      grant_type: 'fb_exchange_token',
      client_id: clientId,
      client_secret: clientSecret,
      fb_exchange_token: shortToken,
    }).toString()
  );
  const longData = await longResp.json();
  if (!longResp.ok || longData?.error) {
    return { accessToken: shortToken, expiresIn: tokenData.expires_in as number | undefined };
  }

  return { accessToken: String(longData.access_token || shortToken), expiresIn: longData.expires_in as number | undefined };
}

async function fetchInstagramAccounts(longUserToken: string) {
  const response = await fetch(
    `https://graph.facebook.com/${GRAPH_VERSION}/me/accounts?` +
    new URLSearchParams({
      fields: 'id,name,access_token,instagram_business_account{id,username,name,profile_picture_url}',
      access_token: longUserToken,
    }).toString()
  );
  const data = await response.json();
  if (!response.ok || data?.error) {
    throw new Error(data?.error?.message || 'Failed to fetch Instagram business accounts from pages');
  }

  type RawIg = {
    id?: string;
    username?: string;
    name?: string;
    profile_picture_url?: string | null;
  };
  type RawPage = {
    id?: string;
    name?: string;
    access_token?: string;
    instagram_business_account?: RawIg;
  };

  const pages = Array.isArray(data?.data) ? (data.data as RawPage[]) : [];
  return pages
    .filter((p) => p?.instagram_business_account?.id)
    .map((p) => ({
      pageId: String(p.id || ''),
      pageName: String(p.name || ''),
      pageAccessToken: String(p.access_token || ''),
      igId: String(p.instagram_business_account?.id || ''),
      igUsername: String(p.instagram_business_account?.username || ''),
      igName: String(p.instagram_business_account?.name || p.name || ''),
      igAvatar: p.instagram_business_account?.profile_picture_url || null,
    }));
}

async function refreshLongLivedUserToken(token: string) {
  const clientId = process.env.INSTAGRAM_APP_ID || process.env.FACEBOOK_APP_ID;
  const clientSecret = process.env.INSTAGRAM_APP_SECRET || process.env.FACEBOOK_APP_SECRET;
  if (!clientId || !clientSecret) {
    throw new Error('INSTAGRAM_APP_ID and INSTAGRAM_APP_SECRET are required');
  }

  const response = await fetch(
    `https://graph.facebook.com/${GRAPH_VERSION}/oauth/access_token?` +
    new URLSearchParams({
      grant_type: 'fb_exchange_token',
      client_id: clientId,
      client_secret: clientSecret,
      fb_exchange_token: token,
    }).toString()
  );
  const data = await response.json();
  if (!response.ok || data?.error) {
    throw new Error(data?.error?.message || 'Failed to refresh Instagram long-lived token');
  }

  return { accessToken: String(data.access_token || token), expiresIn: data.expires_in as number | undefined };
}

async function getValidPageAccessToken(account: ConnectedAccount) {
  const tokenExpiresSoon = account.tokenExpiresAt !== null && account.tokenExpiresAt.getTime() <= Date.now() + 1000 * 60 * 60 * 24 * 3;
  if (!tokenExpiresSoon) {
    return decrypt(account.accessTokenEncrypted);
  }

  if (!account.refreshTokenEncrypted) {
    return decrypt(account.accessTokenEncrypted);
  }

  const userToken = decrypt(account.refreshTokenEncrypted);
  const refreshed = await refreshLongLivedUserToken(userToken);
  const candidates = await fetchInstagramAccounts(refreshed.accessToken);
  const selected = candidates.find((c) => c.igId === account.externalAccountId) || candidates[0];
  if (!selected?.pageAccessToken) {
    throw new Error('Instagram token refresh succeeded but no page access token found. Reconnect account.');
  }

  await db.connectedAccount.update({
    where: { id: account.id },
    data: {
      accessTokenEncrypted: encrypt(selected.pageAccessToken),
      refreshTokenEncrypted: encrypt(refreshed.accessToken),
      tokenExpiresAt: refreshed.expiresIn ? new Date(Date.now() + refreshed.expiresIn * 1000) : account.tokenExpiresAt,
    },
  });

  return selected.pageAccessToken;
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
    let pageAccessToken = input.accessToken || '';
    let externalAccountId = input.externalAccountId || '';
    let username = input.username || '';
    let displayName = input.displayName || '';
    let avatarUrl: string | null = null;
    let longUserToken: string | undefined;
    let tokenExpiresAt: Date | null = null;

    if (input.code) {
      const token = await exchangeCodeForUserToken(input.code, input.redirectUri);
      const candidates = await fetchInstagramAccounts(token.accessToken);
      const selected = candidates.find((c) => c.igId === input.externalAccountId) || candidates[0];
      if (!selected) {
        throw new Error('No Instagram business account found for OAuth user');
      }

      pageAccessToken = selected.pageAccessToken;
      externalAccountId = selected.igId;
      username = selected.igUsername;
      displayName = selected.igName;
      avatarUrl = selected.igAvatar;
      longUserToken = token.accessToken;
      tokenExpiresAt = token.expiresIn ? new Date(Date.now() + token.expiresIn * 1000) : null;
    }

    if (!pageAccessToken || !externalAccountId) {
      throw new Error('Instagram connect requires OAuth code or accessToken + externalAccountId');
    }

    const profile = await fetchInstagramUser(pageAccessToken, externalAccountId);

    const account = await db.connectedAccount.upsert({
      where: {
        provider_externalAccountId: {
          provider: Provider.instagram,
          externalAccountId,
        },
      },
      update: {
        userId: input.userId,
        username: username || profile.username || null,
        displayName: displayName || profile.name || profile.username || null,
        avatarUrl: avatarUrl || profile.profile_picture_url || null,
        accessTokenEncrypted: encrypt(pageAccessToken),
        refreshTokenEncrypted: longUserToken ? encrypt(longUserToken) : undefined,
        tokenExpiresAt,
        metadataJson: JSON.stringify({
          ...input.metadata,
          ig_user_id: externalAccountId,
        }),
      },
      create: {
        userId: input.userId,
        provider: Provider.instagram,
        externalAccountId,
        username: username || profile.username || null,
        displayName: displayName || profile.name || profile.username || null,
        avatarUrl: avatarUrl || profile.profile_picture_url || null,
        accessTokenEncrypted: encrypt(pageAccessToken),
        refreshTokenEncrypted: longUserToken ? encrypt(longUserToken) : null,
        tokenExpiresAt,
        metadataJson: JSON.stringify({
          ...input.metadata,
          ig_user_id: externalAccountId,
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

    const accessToken = await getValidPageAccessToken(account);
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
