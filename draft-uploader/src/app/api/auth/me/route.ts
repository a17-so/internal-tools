import { NextResponse } from 'next/server';
import { requireCurrentUser } from '@/lib/auth';
import { sanitizeTikTokAccount } from '@/lib/datastore';

export async function GET() {
  const context = await requireCurrentUser();
  if (!context) {
    return NextResponse.json({ authenticated: false }, { status: 401 });
  }

  const { user, safeUser, store } = context;

  const accounts = user.role === 'admin'
    ? store.tiktokAccounts.map(sanitizeTikTokAccount)
    : store.tiktokAccounts.filter((account) => account.userId === user.id).map(sanitizeTikTokAccount);

  return NextResponse.json({
    authenticated: true,
    user: safeUser,
    accounts,
  });
}
