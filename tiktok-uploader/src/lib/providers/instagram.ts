import { Provider } from '@prisma/client';
import { SocialProvider } from '@/lib/providers/base';

export const instagramProvider: SocialProvider = {
  provider: Provider.instagram,
  async connectAccount() {
    throw new Error('Instagram provider not implemented');
  },
  async getCapabilities() {
    return {
      supportsDraftVideo: false,
      supportsDirectVideo: false,
      supportsPhotoSlideshow: false,
      captionLimit: 2200,
      hashtagLimit: 30,
      raw: { status: 'not_implemented' },
    };
  },
  async upload() {
    throw new Error('Instagram provider not implemented');
  },
  normalizeError(error) {
    return {
      message: error instanceof Error ? error.message : 'Instagram provider not implemented',
      retryable: false,
      raw: error,
    };
  },
};
