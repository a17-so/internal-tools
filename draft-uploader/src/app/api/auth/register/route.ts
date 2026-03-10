import { NextResponse } from 'next/server';
import { createSession, createUser, setSessionCookie } from '@/lib/auth';
import { sanitizeUser } from '@/lib/datastore';

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const username = typeof body?.username === 'string' ? body.username : '';
    const password = typeof body?.password === 'string' ? body.password : '';

    const result = createUser(username, password);
    if ('error' in result) {
      return NextResponse.json({ error: result.error }, { status: 400 });
    }

    const session = createSession(result.user.id);
    await setSessionCookie(session.id);

    return NextResponse.json({ user: sanitizeUser(result.user) });
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Failed to register user';
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
