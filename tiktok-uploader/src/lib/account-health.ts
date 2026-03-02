import { ConnectedAccount } from '@prisma/client';

export type AccountHealth = {
  needsReauth: boolean;
  expiresSoon: boolean;
  tokenExpiresAt: string | null;
  refreshExpiresAt: string | null;
  message: string | null;
};

export function getAccountHealth(account: Pick<ConnectedAccount, 'tokenExpiresAt' | 'refreshExpiresAt' | 'refreshTokenEncrypted'>): AccountHealth {
  const now = Date.now();
  const tokenMs = account.tokenExpiresAt ? account.tokenExpiresAt.getTime() : null;
  const refreshMs = account.refreshExpiresAt ? account.refreshExpiresAt.getTime() : null;
  const hasRefreshToken = Boolean(account.refreshTokenEncrypted);
  const accessExpired = tokenMs !== null && tokenMs <= now;
  const refreshExpired = refreshMs !== null && refreshMs <= now;

  const needsReauth =
    refreshExpired ||
    (accessExpired && !hasRefreshToken);

  const expiresSoon =
    !needsReauth &&
    (
      (hasRefreshToken && refreshMs !== null && refreshMs <= now + 1000 * 60 * 60 * 24 * 3) ||
      (!hasRefreshToken && tokenMs !== null && tokenMs <= now + 1000 * 60 * 60 * 24)
    );

  let message: string | null = null;
  if (needsReauth) {
    message = 'Authentication expired. Reconnect this account.';
  } else if (expiresSoon) {
    message = hasRefreshToken
      ? 'Refresh token expires soon. Reconnect proactively.'
      : 'Access token expires soon and no refresh token is available.';
  }

  return {
    needsReauth,
    expiresSoon,
    tokenExpiresAt: account.tokenExpiresAt ? account.tokenExpiresAt.toISOString() : null,
    refreshExpiresAt: account.refreshExpiresAt ? account.refreshExpiresAt.toISOString() : null,
    message,
  };
}
