import { cookies } from 'next/headers';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import Uploader from '@/components/ui/uploader';

export default async function Home() {
  const cookieStore = await cookies();
  const accessToken = cookieStore.get('tiktok_access_token');
  const isAuthenticated = !!accessToken;

  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-24 bg-zinc-50 dark:bg-zinc-950">
      <div className="z-10 w-full max-w-5xl items-center justify-center font-mono text-sm flex flex-col space-y-8">
        <h1 className="text-4xl font-bold tracking-tight text-zinc-900 dark:text-zinc-50">
          TikTok Draft Uploader
        </h1>

        {!isAuthenticated ? (
          <div className="flex flex-col items-center space-y-4 text-center">
            <p className="text-zinc-500 dark:text-zinc-400 max-w-[600px] text-lg">
              Authenticate with your TikTok account to easily upload videos directly to your drafts from your desktop.
            </p>
            <Button asChild size="lg" className="mt-4">
              <Link href="/api/auth/tiktok">
                Log in with TikTok
              </Link>
            </Button>
          </div>
        ) : (
          <div className="w-full flex justify-center">
            <Uploader />
          </div>
        )}
      </div>
    </main>
  );
}
