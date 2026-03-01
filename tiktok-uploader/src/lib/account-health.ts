import { ConnectedAccount } from '@prisma/client';

export type AccountHealth = {
  needsReauth: boolean;
  expiresSoon: boolean;
  tokenExpiresAt: string | null;
  refreshExpiresAt: string | null;
  message: string | null;
};

export function getAccountHealth(account: Pick<ConnectedAccount, 'tokenExpiresAt' | 'refreshExpiresAt'>): AccountHealth {
  const now = Date.now();
  const tokenMs = account.tokenExpiresAt ? account.tokenExpiresAt.getTime() : null;
  const refreshMs = account.refreshExpiresAt ? account.refreshExpiresAt.getTime() : null;

  const needsReauth =
    (tokenMs !== null && tokenMs <= now) ||
    (refreshMs !== null && refreshMs <= now);

  const expiresSoon =
    !needsReauth &&
    tokenMs !== null &&
    tokenMs <= now + 1000 * 60 * 60 * 24 * 3;

  let message: string | null = null;
  if (needsReauth) {
    message = 'Authentication expired. Reconnect this account.';
  } else if (expiresSoon) {
    message = 'Authentication token expires soon. Reconnect proactively.';
  }

  return {
    needsReauth,
    expiresSoon,
    tokenExpiresAt: account.tokenExpiresAt ? account.tokenExpiresAt.toISOString() : null,
    refreshExpiresAt: account.refreshExpiresAt ? account.refreshExpiresAt.toISOString() : null,
    message,
  };
}
