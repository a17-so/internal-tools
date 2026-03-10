import crypto from 'crypto';
import { cookies } from 'next/headers';
import {
  getStore,
  hashPassword,
  sanitizeUser,
  SESSION_COOKIE,
  SESSION_TTL_SECONDS,
  updateStore,
  type SessionRecord,
  type UserRecord,
} from '@/lib/datastore';

function nowIso() {
  return new Date().toISOString();
}

function isExpired(iso: string) {
  return new Date(iso).getTime() <= Date.now();
}

function addSeconds(date: Date, seconds: number) {
  return new Date(date.getTime() + seconds * 1000);
}

export async function setSessionCookie(sessionId: string) {
  const cookieStore = await cookies();
  cookieStore.set(SESSION_COOKIE, sessionId, {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    maxAge: SESSION_TTL_SECONDS,
    path: '/',
    sameSite: 'lax',
  });
}

export async function clearSessionCookie() {
  const cookieStore = await cookies();
  cookieStore.set(SESSION_COOKIE, '', {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    maxAge: 0,
    path: '/',
    sameSite: 'lax',
  });
}

export function createSession(userId: string) {
  const id = crypto.randomBytes(32).toString('hex');
  const createdAt = nowIso();
  const expiresAt = addSeconds(new Date(), SESSION_TTL_SECONDS).toISOString();
  const session: SessionRecord = { id, userId, createdAt, expiresAt };
  updateStore((store) => {
    store.sessions = store.sessions.filter((item) => !isExpired(item.expiresAt));
    store.sessions.push(session);
  });
  return session;
}

export function verifyPassword(user: UserRecord, password: string) {
  const computed = hashPassword(password, user.passwordSalt);
  return computed.hash === user.passwordHash;
}

export async function getCurrentSession() {
  const cookieStore = await cookies();
  const sessionId = cookieStore.get(SESSION_COOKIE)?.value;
  if (!sessionId) {
    return null;
  }

  const store = getStore();
  const session = store.sessions.find((item) => item.id === sessionId);
  if (!session || isExpired(session.expiresAt)) {
    return null;
  }

  const user = store.users.find((item) => item.id === session.userId);
  if (!user) {
    return null;
  }

  return { session, user, store };
}

export async function requireCurrentUser() {
  const data = await getCurrentSession();
  if (!data) {
    return null;
  }

  return { ...data, safeUser: sanitizeUser(data.user) };
}

export function createUser(username: string, password: string) {
  const normalized = username.trim();
  if (!normalized) {
    return { error: 'Username is required' } as const;
  }

  if (password.length < 8) {
    return { error: 'Password must be at least 8 characters' } as const;
  }

  const currentStore = getStore();
  const exists = currentStore.users.some((user) => user.username.toLowerCase() === normalized.toLowerCase());
  if (exists) {
    return { error: 'Username is already taken' } as const;
  }

  const credentials = hashPassword(password);
  const user: UserRecord = {
    id: crypto.randomUUID(),
    username: normalized,
    role: 'user',
    passwordSalt: credentials.salt,
    passwordHash: credentials.hash,
    createdAt: nowIso(),
  };

  updateStore((store) => {
    store.users.push(user);
  });

  return { user } as const;
}
