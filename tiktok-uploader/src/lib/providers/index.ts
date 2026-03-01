import { Provider } from '@prisma/client';
import { SocialProvider } from '@/lib/providers/base';
import { instagramProvider } from '@/lib/providers/instagram';
import { tiktokProvider } from '@/lib/providers/tiktok';

const providers = new Map<Provider, SocialProvider>([
  [Provider.tiktok, tiktokProvider],
  [Provider.instagram, instagramProvider],
]);

export function getProvider(provider: Provider): SocialProvider {
  const impl = providers.get(provider);
  if (!impl) {
    throw new Error(`Provider ${provider} is not implemented`);
  }
  return impl;
}
