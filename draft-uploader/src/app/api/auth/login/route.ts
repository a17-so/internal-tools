import { NextResponse } from 'next/server';
import { createSession, setSessionCookie, verifyPassword } from '@/lib/auth';
import { getStore, sanitizeUser } from '@/lib/datastore';

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const username = typeof body?.username === 'string' ? body.username.trim() : '';
    const password = typeof body?.password === 'string' ? body.password : '';

    if (!username || !password) {
      return NextResponse.json({ error: 'Username and password are required' }, { status: 400 });
    }

    const store = getStore();
    const user = store.users.find((item) => item.username.toLowerCase() === username.toLowerCase());

    if (!user || !verifyPassword(user, password)) {
      return NextResponse.json({ error: 'Invalid username or password' }, { status: 401 });
    }

    const session = createSession(user.id);
    await setSessionCookie(session.id);

    return NextResponse.json({ user: sanitizeUser(user) });
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Failed to login';
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
