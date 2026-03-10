import Link from 'next/link';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { requireCurrentUser } from '@/lib/auth';

type TikTokUser = {
  open_id?: string;
  union_id?: string;
  avatar_url?: string;
  display_name?: string;
  bio_description?: string;
  profile_deep_link?: string;
  is_verified?: boolean;
  follower_count?: number;
  following_count?: number;
  likes_count?: number;
  video_count?: number;
};

type TikTokVideo = {
  id?: string;
  title?: string;
  video_description?: string;
  create_time?: number;
  view_count?: number;
  like_count?: number;
  comment_count?: number;
  share_count?: number;
};

async function requestTikTok(path: string, accessToken: string) {
  const response = await fetch(`https://open.tiktokapis.com${path}`, {
    headers: { Authorization: `Bearer ${accessToken}` },
    cache: 'no-store',
  });
  return response.json();
}

export default async function AnalyticsPage({ searchParams }: { searchParams: Promise<{ accountId?: string }> }) {
  const params = await searchParams;
  const context = await requireCurrentUser();

  if (!context) {
    return (
      <main className="mx-auto flex min-h-screen w-full max-w-4xl flex-col gap-6 px-6 py-12">
        <h1 className="text-3xl font-semibold">Analytics</h1>
        <p className="text-sm text-zinc-600">You need to log in first.</p>
        <Link href="/" className="text-sm underline underline-offset-4">Back to home</Link>
      </main>
    );
  }

  const visibleAccounts = context.user.role === 'admin'
    ? context.store.tiktokAccounts
    : context.store.tiktokAccounts.filter((account) => account.userId === context.user.id);
  const selected = params.accountId
    ? visibleAccounts.find((account) => account.id === params.accountId)
    : visibleAccounts[0];

  if (!selected) {
    return (
      <main className="mx-auto flex min-h-screen w-full max-w-4xl flex-col gap-6 px-6 py-12">
        <h1 className="text-3xl font-semibold">Analytics</h1>
        <p className="text-sm text-zinc-600">Connect at least one TikTok account first.</p>
        <Link href="/" className="text-sm underline underline-offset-4">Back to home</Link>
      </main>
    );
  }

  const accessToken = selected.accessToken;

  const userData = await requestTikTok(
    '/v2/user/info/?fields=open_id,union_id,avatar_url,display_name,bio_description,profile_deep_link,is_verified,follower_count,following_count,likes_count,video_count',
    accessToken
  );

  const videoData = await requestTikTok(
    '/v2/video/list/?fields=id,title,video_description,create_time,view_count,like_count,comment_count,share_count&max_count=10',
    accessToken
  );

  const userError = userData?.error?.code !== 'ok' ? userData?.error?.message || 'Unable to load user analytics' : null;
  const videosError = videoData?.error?.code !== 'ok' ? videoData?.error?.message || 'Unable to load video list' : null;

  const user = (userData?.data?.user || {}) as TikTokUser;
  const videos = (videoData?.data?.videos || []) as TikTokVideo[];

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-5xl flex-col gap-5 px-6 py-10">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-semibold">TikTok Analytics</h1>
        <Link href="/" className="text-sm underline underline-offset-4">Back to uploader</Link>
      </div>
      <p className="text-sm text-zinc-600">Account: {selected.displayName} ({selected.openId})</p>

      <Card>
        <CardHeader>
          <CardTitle>Account Overview</CardTitle>
          <CardDescription>Uses scopes: user.info.basic, user.info.profile, user.info.stats</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {userError ? <p className="text-sm text-rose-600">{userError}</p> : null}
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div><p className="text-xs text-zinc-500">Display name</p><p className="text-sm font-medium">{user.display_name || '-'}</p></div>
            <div><p className="text-xs text-zinc-500">Followers</p><p className="text-sm font-medium">{user.follower_count ?? '-'}</p></div>
            <div><p className="text-xs text-zinc-500">Following</p><p className="text-sm font-medium">{user.following_count ?? '-'}</p></div>
            <div><p className="text-xs text-zinc-500">Likes</p><p className="text-sm font-medium">{user.likes_count ?? '-'}</p></div>
            <div><p className="text-xs text-zinc-500">Video count</p><p className="text-sm font-medium">{user.video_count ?? '-'}</p></div>
            <div><p className="text-xs text-zinc-500">Verified</p><p className="text-sm font-medium">{user.is_verified ? 'Yes' : 'No'}</p></div>
          </div>
          {user.profile_deep_link ? (
            <a className="text-sm underline underline-offset-4" href={user.profile_deep_link} target="_blank" rel="noreferrer">
              Open TikTok Profile
            </a>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Recent Videos</CardTitle>
          <CardDescription>Uses scope: video.list</CardDescription>
        </CardHeader>
        <CardContent>
          {videosError ? <p className="text-sm text-rose-600">{videosError}</p> : null}
          {!videosError && videos.length === 0 ? <p className="text-sm text-zinc-600">No public videos found.</p> : null}
          <div className="space-y-2">
            {videos.map((video) => (
              <div key={video.id} className="rounded-md border p-3">
                <p className="text-sm font-medium">{video.title || video.video_description || video.id}</p>
                <p className="mt-1 text-xs text-zinc-500">
                  {video.create_time ? new Date(video.create_time * 1000).toLocaleString() : 'Unknown date'} ·
                  {' '}Views: {video.view_count ?? 0} · Likes: {video.like_count ?? 0} · Comments: {video.comment_count ?? 0}
                </p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </main>
  );
}
