import { NextResponse } from 'next/server';
import { cookies } from 'next/headers';
import { clearSessionCookie } from '@/lib/auth';
import { SESSION_COOKIE, updateStore } from '@/lib/datastore';

export async function POST() {
  const cookieStore = await cookies();
  const sessionId = cookieStore.get(SESSION_COOKIE)?.value;

  if (sessionId) {
    updateStore((store) => {
      store.sessions = store.sessions.filter((item) => item.id !== sessionId);
    });
  }

  await clearSessionCookie();
  return NextResponse.json({ success: true });
}
