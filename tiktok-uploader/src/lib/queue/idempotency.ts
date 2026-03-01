import crypto from 'crypto';
import { Provider, UploadMode, UploadPostType } from '@prisma/client';

export function buildIdempotencyKey(input: {
  mediaHashes: string[];
  caption: string;
  accountId: string;
  provider: Provider;
  mode: UploadMode;
  postType: UploadPostType;
  clientRef?: string;
}) {
  const payload = {
    ...input,
    caption: input.caption.trim(),
    mediaHashes: [...input.mediaHashes].sort(),
  };

  return crypto.createHash('sha256').update(JSON.stringify(payload)).digest('hex');
}

export function isLikelyMimeType(filePath: string): string {
  const lower = filePath.toLowerCase();
  if (lower.endsWith('.mp4')) return 'video/mp4';
  if (lower.endsWith('.webm')) return 'video/webm';
  if (lower.endsWith('.mov')) return 'video/quicktime';
  if (lower.endsWith('.jpg') || lower.endsWith('.jpeg')) return 'image/jpeg';
  if (lower.endsWith('.png')) return 'image/png';
  if (lower.endsWith('.webp')) return 'image/webp';
  return 'application/octet-stream';
}
