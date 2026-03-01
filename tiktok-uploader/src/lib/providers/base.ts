import { ConnectedAccount, Provider, UploadAsset, UploadJob } from '@prisma/client';
import { ProviderCapabilities, ProviderUploadResult } from '@/lib/types';

export type ProviderError = {
  message: string;
  retryable: boolean;
  httpStatus?: number;
  providerCode?: string;
  raw?: unknown;
};

export interface SocialProvider {
  provider: Provider;
  connectAccount(input: {
    code: string;
    codeVerifier?: string;
    redirectUri: string;
    userId: string;
  }): Promise<ConnectedAccount>;
  getCapabilities(account: ConnectedAccount): Promise<ProviderCapabilities>;
  upload(job: UploadJob, account: ConnectedAccount, assets: UploadAsset[]): Promise<ProviderUploadResult>;
  normalizeError(error: unknown): ProviderError;
}
