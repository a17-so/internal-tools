import crypto from 'crypto';
import fs from 'fs';
import path from 'path';

export type Role = 'admin' | 'user';

export type UserRecord = {
  id: string;
  username: string;
  role: Role;
  passwordSalt: string;
  passwordHash: string;
  createdAt: string;
};

export type SessionRecord = {
  id: string;
  userId: string;
  createdAt: string;
  expiresAt: string;
};

export type TikTokAccountRecord = {
  id: string;
  userId: string;
  openId: string;
  displayName: string;
  accessToken: string;
  refreshToken?: string;
  accessTokenExpiresAt?: string;
  refreshTokenExpiresAt?: string;
  source: 'oauth' | 'seeded';
  createdAt: string;
  updatedAt: string;
};

export type UploadPostType = 'video' | 'slideshow';
export type UploadJobStatus = 'queued' | 'processing' | 'completed' | 'failed';
export type UploadBatchStatus = 'queued' | 'processing' | 'completed' | 'failed';

export type StagedMediaFileRecord = {
  id: string;
  originalName: string;
  mimeType: string;
  size: number;
  order: number;
  relativePath?: string;
  stagedPath: string;
};

export type StagedUploadRecord = {
  id: string;
  userId: string;
  tiktokAccountId: string;
  postType: UploadPostType;
  files: StagedMediaFileRecord[];
  createdAt: string;
  expiresAt: string;
  consumedAt?: string;
};

export type UploadJobRecord = {
  id: string;
  batchId: string;
  userId: string;
  tiktokAccountId: string;
  postType: UploadPostType;
  stagedUploadId: string;
  caption?: string;
  status: UploadJobStatus;
  createdAt: string;
  updatedAt: string;
  startedAt?: string;
  completedAt?: string;
  failedAt?: string;
  error?: string;
  tiktokPublishId?: string;
  usedVideoFallback?: boolean;
};

export type UploadBatchRecord = {
  id: string;
  userId: string;
  tiktokAccountId: string;
  createdAt: string;
  updatedAt: string;
  status: UploadBatchStatus;
  totalJobs: number;
  queuedJobs: number;
  completedJobs: number;
  failedJobs: number;
};

type SeedInternalTikTokAccount = {
  openId: string;
  displayName?: string;
  accessToken: string;
  refreshToken?: string;
  accessTokenExpiresAt?: string;
  refreshTokenExpiresAt?: string;
};

type DataStore = {
  users: UserRecord[];
  sessions: SessionRecord[];
  tiktokAccounts: TikTokAccountRecord[];
  stagedUploads: StagedUploadRecord[];
  uploadJobs: UploadJobRecord[];
  uploadBatches: UploadBatchRecord[];
};

const DATA_DIR = path.join(process.cwd(), 'data');
const DATA_PATH = path.join(DATA_DIR, 'store.json');

function ensureDataFile() {
  if (!fs.existsSync(DATA_DIR)) {
    fs.mkdirSync(DATA_DIR, { recursive: true });
  }

  if (!fs.existsSync(DATA_PATH)) {
    const initial: DataStore = {
      users: [],
      sessions: [],
      tiktokAccounts: [],
      stagedUploads: [],
      uploadJobs: [],
      uploadBatches: [],
    };
    fs.writeFileSync(DATA_PATH, JSON.stringify(initial, null, 2), 'utf8');
  }
}

function pruneExpiredStagedUploads(store: DataStore): DataStore {
  const now = Date.now();
  const retained = store.stagedUploads.filter((upload) => new Date(upload.expiresAt).getTime() > now);
  if (retained.length !== store.stagedUploads.length) {
    store.stagedUploads = retained;
  }
  return store;
}

function readStore(): DataStore {
  ensureDataFile();
  const raw = fs.readFileSync(DATA_PATH, 'utf8');
  try {
    const parsed = JSON.parse(raw) as Partial<DataStore>;
    return pruneExpiredStagedUploads({
      users: parsed.users ?? [],
      sessions: parsed.sessions ?? [],
      tiktokAccounts: parsed.tiktokAccounts ?? [],
      stagedUploads: parsed.stagedUploads ?? [],
      uploadJobs: parsed.uploadJobs ?? [],
      uploadBatches: parsed.uploadBatches ?? [],
    });
  } catch {
    const fallback: DataStore = {
      users: [],
      sessions: [],
      tiktokAccounts: [],
      stagedUploads: [],
      uploadJobs: [],
      uploadBatches: [],
    };
    fs.writeFileSync(DATA_PATH, JSON.stringify(fallback, null, 2), 'utf8');
    return fallback;
  }
}

function writeStore(store: DataStore) {
  fs.writeFileSync(DATA_PATH, JSON.stringify(store, null, 2), 'utf8');
}

export function hashPassword(password: string, salt?: string) {
  const actualSalt = salt ?? crypto.randomBytes(16).toString('hex');
  const derived = crypto.scryptSync(password, actualSalt, 64).toString('hex');
  return { salt: actualSalt, hash: derived };
}

function createAdminIfMissing(store: DataStore): DataStore {
  const adminUsername = process.env.ADMIN_USERNAME?.trim() || 'A17';
  const adminPassword = process.env.ADMIN_PASSWORD?.trim() || 'A17ChangeMe!';
  const adminExists = store.users.some((user) => user.role === 'admin' || user.username === adminUsername);

  if (!adminExists) {
    const credentials = hashPassword(adminPassword);
    const adminUser: UserRecord = {
      id: crypto.randomUUID(),
      username: adminUsername,
      role: 'admin',
      passwordSalt: credentials.salt,
      passwordHash: credentials.hash,
      createdAt: new Date().toISOString(),
    };
    store.users.push(adminUser);
  }

  return store;
}

function parseSeededAccounts(): SeedInternalTikTokAccount[] {
  const raw = process.env.INTERNAL_TIKTOK_ACCOUNTS?.trim();
  if (!raw) {
    return [];
  }

  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) {
      return [];
    }

    return parsed.filter((item): item is SeedInternalTikTokAccount => {
      if (!item || typeof item !== 'object') {
        return false;
      }

      const candidate = item as Record<string, unknown>;
      return typeof candidate.openId === 'string' && typeof candidate.accessToken === 'string';
    });
  } catch {
    return [];
  }
}

function seedInternalAccounts(store: DataStore): DataStore {
  const admin = store.users.find((user) => user.role === 'admin');
  if (!admin) {
    return store;
  }

  const accounts = parseSeededAccounts();
  if (accounts.length === 0) {
    return store;
  }

  const now = new Date().toISOString();
  for (const account of accounts) {
    const existing = store.tiktokAccounts.find(
      (record) => record.userId === admin.id && record.openId === account.openId
    );

    if (!existing) {
      store.tiktokAccounts.push({
        id: crypto.randomUUID(),
        userId: admin.id,
        openId: account.openId,
        displayName: account.displayName || account.openId,
        accessToken: account.accessToken,
        refreshToken: account.refreshToken,
        accessTokenExpiresAt: account.accessTokenExpiresAt,
        refreshTokenExpiresAt: account.refreshTokenExpiresAt,
        source: 'seeded',
        createdAt: now,
        updatedAt: now,
      });
    }
  }

  return store;
}

export function getStore(): DataStore {
  const loaded = readStore();
  const withAdmin = createAdminIfMissing(loaded);
  const withSeeds = seedInternalAccounts(withAdmin);
  writeStore(withSeeds);
  return withSeeds;
}

export function updateStore(mutator: (store: DataStore) => DataStore | void): DataStore {
  const loaded = getStore();
  const maybeUpdated = mutator(loaded);
  const next = maybeUpdated ?? loaded;
  writeStore(next);
  return next;
}

export function sanitizeTikTokAccount(account: TikTokAccountRecord) {
  return {
    id: account.id,
    userId: account.userId,
    openId: account.openId,
    displayName: account.displayName,
    source: account.source,
    createdAt: account.createdAt,
    updatedAt: account.updatedAt,
  };
}

export function sanitizeUser(user: UserRecord) {
  return {
    id: user.id,
    username: user.username,
    role: user.role,
    createdAt: user.createdAt,
  };
}

export const SESSION_COOKIE = 'du_session';
export const SESSION_TTL_SECONDS = 60 * 60 * 24 * 30;
