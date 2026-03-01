import fs from 'fs/promises';
import { ConnectedAccount, Provider, UploadAsset, UploadJob, UploadMode, UploadPostType } from '@prisma/client';
import { db } from '@/lib/db';
import { decrypt, encrypt } from '@/lib/crypto';
import { ProviderUploadResult } from '@/lib/types';
import { ProviderError, SocialProvider } from '@/lib/providers/base';

const GRAPH_VERSION = process.env.FACEBOOK_GRAPH_VERSION || 'v24.0';

async function exchangeCodeForUserToken(code: string, redirectUri?: string) {
  const clientId = process.env.FACEBOOK_APP_ID;
  const clientSecret = process.env.FACEBOOK_APP_SECRET;
  const callback = redirectUri || `${process.env.NEXT_PUBLIC_APP_URL}/api/auth/facebook/callback`;

  if (!clientId || !clientSecret) {
    throw new Error('FACEBOOK_APP_ID and FACEBOOK_APP_SECRET are required');
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
    throw new Error(tokenData?.error?.message || 'Failed to exchange Facebook OAuth code');
  }

  const shortToken = String(tokenData.access_token || '');
  if (!shortToken) {
    throw new Error('Facebook OAuth exchange did not return access token');
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

async function fetchPages(userToken: string) {
  const response = await fetch(
    `https://graph.facebook.com/${GRAPH_VERSION}/me/accounts?` +
    new URLSearchParams({
      fields: 'id,name,access_token,picture',
      access_token: userToken,
    }).toString()
  );
  const data = await response.json();
  if (!response.ok || data?.error) {
    throw new Error(data?.error?.message || 'Failed to fetch Facebook pages');
  }

  type RawPicture = { data?: { url?: string | null } };
  type RawPage = { id?: string; name?: string; access_token?: string; picture?: RawPicture };

  const pages = Array.isArray(data?.data) ? (data.data as RawPage[]) : [];
  return pages.map((p) => ({
    id: String(p.id || ''),
    name: String(p.name || ''),
    accessToken: String(p.access_token || ''),
    avatar: p?.picture?.data?.url || null,
  }));
}

async function refreshLongLivedUserToken(token: string) {
  const clientId = process.env.FACEBOOK_APP_ID;
  const clientSecret = process.env.FACEBOOK_APP_SECRET;
  if (!clientId || !clientSecret) {
    throw new Error('FACEBOOK_APP_ID and FACEBOOK_APP_SECRET are required');
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
    throw new Error(data?.error?.message || 'Failed to refresh Facebook long-lived token');
  }

  return { accessToken: String(data.access_token || token), expiresIn: data.expires_in as number | undefined };
}

async function fetchPageProfile(accessToken: string, pageId: string) {
  const response = await fetch(`https://graph.facebook.com/${GRAPH_VERSION}/${pageId}?fields=id,name,picture&access_token=${encodeURIComponent(accessToken)}`);
  const data = await response.json();
  if (!response.ok || data?.error) {
    throw new Error(data?.error?.message || 'Failed to fetch Facebook page profile');
  }
  return data;
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
  const pages = await fetchPages(refreshed.accessToken);
  const selected = pages.find((p) => p.id === account.externalAccountId) || pages[0];
  if (!selected?.accessToken) {
    throw new Error('Facebook token refresh succeeded but no page token available. Reconnect account.');
  }

  await db.connectedAccount.update({
    where: { id: account.id },
    data: {
      accessTokenEncrypted: encrypt(selected.accessToken),
      refreshTokenEncrypted: encrypt(refreshed.accessToken),
      tokenExpiresAt: refreshed.expiresIn ? new Date(Date.now() + refreshed.expiresIn * 1000) : account.tokenExpiresAt,
    },
  });

  return selected.accessToken;
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
    let pageAccessToken = input.accessToken || '';
    let pageId = input.externalAccountId || '';
    let displayName = input.displayName || '';
    let avatarUrl: string | null = null;
    let longUserToken: string | undefined;
    let tokenExpiresAt: Date | null = null;

    if (input.code) {
      const token = await exchangeCodeForUserToken(input.code, input.redirectUri);
      const pages = await fetchPages(token.accessToken);
      const selected = pages.find((p) => p.id === input.externalAccountId) || pages[0];
      if (!selected) {
        throw new Error('No Facebook pages found for OAuth user');
      }

      pageAccessToken = selected.accessToken;
      pageId = selected.id;
      displayName = displayName || selected.name;
      avatarUrl = selected.avatar;
      longUserToken = token.accessToken;
      tokenExpiresAt = token.expiresIn ? new Date(Date.now() + token.expiresIn * 1000) : null;
    }

    if (!pageAccessToken || !pageId) {
      throw new Error('Facebook connect requires OAuth code or accessToken + externalAccountId (page id)');
    }

    const page = await fetchPageProfile(pageAccessToken, pageId);

    const account = await db.connectedAccount.upsert({
      where: {
        provider_externalAccountId: {
          provider: Provider.facebook,
          externalAccountId: pageId,
        },
      },
      update: {
        userId: input.userId,
        username: page.name || null,
        displayName: displayName || page.name || null,
        avatarUrl: avatarUrl || page.picture?.data?.url || null,
        accessTokenEncrypted: encrypt(pageAccessToken),
        refreshTokenEncrypted: longUserToken ? encrypt(longUserToken) : undefined,
        tokenExpiresAt,
        metadataJson: JSON.stringify({
          ...input.metadata,
          page_id: pageId,
        }),
      },
      create: {
        userId: input.userId,
        provider: Provider.facebook,
        externalAccountId: pageId,
        username: page.name || null,
        displayName: displayName || page.name || null,
        avatarUrl: avatarUrl || page.picture?.data?.url || null,
        accessTokenEncrypted: encrypt(pageAccessToken),
        refreshTokenEncrypted: longUserToken ? encrypt(longUserToken) : null,
        tokenExpiresAt,
        metadataJson: JSON.stringify({
          ...input.metadata,
          page_id: pageId,
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

    const accessToken = await getValidPageAccessToken(account);
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
