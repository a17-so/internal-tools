import { NextResponse } from 'next/server';
import { requireCurrentUser } from '@/lib/auth';
import { sanitizeTikTokAccount } from '@/lib/datastore';

export async function GET() {
  const context = await requireCurrentUser();
  if (!context) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const { user, store } = context;
  const accounts = user.role === 'admin'
    ? store.tiktokAccounts.map(sanitizeTikTokAccount)
    : store.tiktokAccounts
      .filter((item) => item.userId === user.id)
      .map(sanitizeTikTokAccount);

  return NextResponse.json({ accounts });
}
