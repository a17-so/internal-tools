export function normalizeBaseUrl(input: string | undefined, fallback: string) {
  const value = (input || fallback).trim();
  return value.replace(/\/+$/, '');
}

export function buildCallbackUrl(baseUrl: string, callbackPath = '/api/auth/callback') {
  return `${baseUrl}${callbackPath.startsWith('/') ? callbackPath : `/${callbackPath}`}`;
}
