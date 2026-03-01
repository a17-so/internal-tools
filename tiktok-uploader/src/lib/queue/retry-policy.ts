import { Provider } from '@prisma/client';

export type RetryPolicy = {
  maxRetries: number;
  baseDelayMs: number;
  maxDelayMs: number;
  jitterMs: number;
};

function envInt(name: string, fallback: number): number {
  const raw = process.env[name];
  if (!raw) return fallback;
  const n = Number(raw);
  return Number.isFinite(n) && n >= 0 ? n : fallback;
}

const defaults: Record<Provider, RetryPolicy> = {
  tiktok: { maxRetries: envInt('RETRY_MAX_TIKTOK', 4), baseDelayMs: envInt('RETRY_BASE_MS_TIKTOK', 1500), maxDelayMs: envInt('RETRY_MAX_MS_TIKTOK', 90000), jitterMs: envInt('RETRY_JITTER_MS_TIKTOK', 1000) },
  instagram: { maxRetries: envInt('RETRY_MAX_INSTAGRAM', 3), baseDelayMs: envInt('RETRY_BASE_MS_INSTAGRAM', 2500), maxDelayMs: envInt('RETRY_MAX_MS_INSTAGRAM', 120000), jitterMs: envInt('RETRY_JITTER_MS_INSTAGRAM', 1500) },
  youtube: { maxRetries: envInt('RETRY_MAX_YOUTUBE', 4), baseDelayMs: envInt('RETRY_BASE_MS_YOUTUBE', 2000), maxDelayMs: envInt('RETRY_MAX_MS_YOUTUBE', 180000), jitterMs: envInt('RETRY_JITTER_MS_YOUTUBE', 1500) },
  facebook: { maxRetries: envInt('RETRY_MAX_FACEBOOK', 3), baseDelayMs: envInt('RETRY_BASE_MS_FACEBOOK', 2000), maxDelayMs: envInt('RETRY_MAX_MS_FACEBOOK', 120000), jitterMs: envInt('RETRY_JITTER_MS_FACEBOOK', 1200) },
};

export function getRetryPolicy(provider: Provider): RetryPolicy {
  return defaults[provider];
}

export function getRetryDelayMs(provider: Provider, attemptNo: number): number {
  const policy = getRetryPolicy(provider);
  const exp = Math.max(0, attemptNo - 1);
  const base = Math.min(policy.maxDelayMs, policy.baseDelayMs * Math.pow(2, exp));
  const jitter = Math.floor(Math.random() * policy.jitterMs);
  return Math.min(policy.maxDelayMs, base + jitter);
}
