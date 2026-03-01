import { Provider, UploadMode, UploadPostType } from '@prisma/client';

export type QueueCreateAssetInput = {
  type: 'video' | 'image';
  filePath: string;
  mimeType?: string;
  sizeBytes: number;
  sortOrder: number;
};

export type QueueCreateJobInput = {
  userId: string;
  batchId?: string;
  connectedAccountId: string;
  provider: Provider;
  mode: UploadMode;
  postType: UploadPostType;
  caption: string;
  idempotencyKey: string;
  scheduledAt?: Date | null;
  assets: QueueCreateAssetInput[];
};

export type ProviderCapabilities = {
  supportsDraftVideo: boolean;
  supportsDirectVideo: boolean;
  supportsPhotoSlideshow: boolean;
  captionLimit: number;
  hashtagLimit: number;
  raw?: unknown;
};

export type ProviderUploadResult = {
  externalPostId?: string;
  raw?: unknown;
};
