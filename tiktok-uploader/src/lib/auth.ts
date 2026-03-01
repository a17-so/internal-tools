import bcrypt from 'bcryptjs';
import { cookies, headers } from 'next/headers';
import { db } from '@/lib/db';
import { randomToken, sha256 } from '@/lib/crypto';

const SESSION_COOKIE = 'uploader_session';

function isTruthy(value: string | undefined) {
  if (!value) return false;
  const normalized = value.trim().toLowerCase();
  return normalized === '1' || normalized === 'true' || normalized === 'yes' || normalized === 'on';
}

function isFalsy(value: string | undefined) {
  if (!value) return false;
  const normalized = value.trim().toLowerCase();
  return normalized === '0' || normalized === 'false' || normalized === 'no' || normalized === 'off';
}

export function isAuthBypassEnabled() {
  if (isTruthy(process.env.AUTH_BYPASS)) return true;
  if (isFalsy(process.env.AUTH_BYPASS)) return false;
  return process.env.NODE_ENV !== 'production';
}

export type AuthUser = {
  id: string;
  email: string;
  name: string | null;
};

async function ensureBypassUser() {
  const email = process.env.AUTH_BYPASS_EMAIL || process.env.APP_USER_EMAIL || 'operator@local';
  const existing = await db.user.findUnique({ where: { email } });
  if (existing) return existing;

  const passwordHash = await bcrypt.hash(randomToken('bypass'), 8);
  return db.user.create({
    data: {
      email,
      name: 'Bypass Operator',
      passwordHash,
    },
  });
}

export async function ensureDefaultUser() {
  const email = process.env.APP_USER_EMAIL;
  const password = process.env.APP_USER_PASSWORD;

  if (!email || !password) {
    throw new Error('APP_USER_EMAIL and APP_USER_PASSWORD are required');
  }

  const existing = await db.user.findUnique({ where: { email } });
  if (existing) return existing;

  const passwordHash = await bcrypt.hash(password, 12);
  return db.user.create({
    data: {
      email,
      name: 'Internal Operator',
      passwordHash,
    },
  });
}

export async function loginWithPassword(email: string, password: string) {
  if (isAuthBypassEnabled()) {
    const bypassUser = await ensureBypassUser();
    return { id: bypassUser.id, email: bypassUser.email, name: bypassUser.name } satisfies AuthUser;
  }

  await ensureDefaultUser();

  const user = await db.user.findUnique({ where: { email } });
  if (!user) return null;

  const valid = await bcrypt.compare(password, user.passwordHash);
  if (!valid) return null;

  const rawToken = randomToken('sess');
  const tokenHash = sha256(rawToken);
  const expiresAt = new Date(Date.now() + 1000 * 60 * 60 * 24 * 14);

  await db.session.create({
    data: {
      userId: user.id,
      tokenHash,
      expiresAt,
    },
  });

  const cookieStore = await cookies();
  cookieStore.set(SESSION_COOKIE, rawToken, {
    httpOnly: true,
    sameSite: 'lax',
    secure: process.env.NODE_ENV === 'production',
    path: '/',
    expires: expiresAt,
  });

  return { id: user.id, email: user.email, name: user.name } satisfies AuthUser;
}

export async function logoutCurrentSession() {
  const cookieStore = await cookies();
  const rawToken = cookieStore.get(SESSION_COOKIE)?.value;
  if (rawToken) {
    await db.session.deleteMany({ where: { tokenHash: sha256(rawToken) } });
  }
  cookieStore.delete(SESSION_COOKIE);
}

async function getUserBySession(): Promise<AuthUser | null> {
  const cookieStore = await cookies();
  const rawToken = cookieStore.get(SESSION_COOKIE)?.value;
  if (!rawToken) return null;

  const tokenHash = sha256(rawToken);
  const now = new Date();

  const session = await db.session.findFirst({
    where: { tokenHash, expiresAt: { gt: now } },
    include: { user: true },
  });

  if (!session) {
    cookieStore.delete(SESSION_COOKIE);
    return null;
  }

  await db.session.update({
    where: { id: session.id },
    data: { lastUsedAt: now },
  });

  return {
    id: session.user.id,
    email: session.user.email,
    name: session.user.name,
  };
}

async function getUserByApiKey(): Promise<AuthUser | null> {
  const h = await headers();
  const authHeader = h.get('authorization');
  const xApiKey = h.get('x-api-key');
  const candidate = xApiKey || (authHeader?.startsWith('Bearer ') ? authHeader.slice(7) : null);

  if (!candidate) return null;

  const keyHash = sha256(candidate);
  const key = await db.apiKey.findFirst({
    where: {
      keyHash,
      revokedAt: null,
    },
    include: { user: true },
  });

  if (!key) return null;

  await db.apiKey.update({
    where: { id: key.id },
    data: { lastUsedAt: new Date() },
  });

  return {
    id: key.user.id,
    email: key.user.email,
    name: key.user.name,
  };
}

export async function requireAuth(): Promise<AuthUser> {
  if (isAuthBypassEnabled()) {
    const bypassUser = await ensureBypassUser();
    return {
      id: bypassUser.id,
      email: bypassUser.email,
      name: bypassUser.name,
    };
  }

  const bySession = await getUserBySession();
  if (bySession) return bySession;

  const byApiKey = await getUserByApiKey();
  if (byApiKey) return byApiKey;

  throw new Error('UNAUTHORIZED');
}

export async function getOptionalAuth(): Promise<AuthUser | null> {
  if (isAuthBypassEnabled()) {
    const bypassUser = await ensureBypassUser();
    return {
      id: bypassUser.id,
      email: bypassUser.email,
      name: bypassUser.name,
    };
  }

  const bySession = await getUserBySession();
  if (bySession) return bySession;
  return getUserByApiKey();
}

export async function createApiKey(userId: string, name: string) {
  const token = randomToken('upl');
  const keyHash = sha256(token);
  const keyPrefix = token.slice(0, 12);

  const row = await db.apiKey.create({
    data: {
      userId,
      name,
      keyPrefix,
      keyHash,
    },
  });

  return {
    ...row,
    token,
  };
}
